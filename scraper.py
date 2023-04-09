import subprocess
from bs4 import BeautifulSoup
from enum import Enum
import json
import re
import urllib.parse
import os

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

#used for testing
def printSoup(soup):
    i = 0
    for tag in soup:
        print(f"\n\ntag #{i}")
        print(tag)
        i += 1

def printUnplannedError(e):
    print("Unplanned error")
    print(e)

def goldilocks(soup):
    head = soup.find("h1")

    if head and head.text == "Object Moved":
        raise Exception("Failed getting this data. The house moved")
    
    return soup

#this is used for when you have a tr and want to parse three things and get the bold value and the unbold field
def boldStrategy(data, soupArr):
    try:
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
    except Exception as e:
        printUnplannedError(e)

#this is for when you have a perfect every other array of field then value
def everyOtherStrategy(data, soupArr):
    try:
        for tag in soupArr[::2]:
            value = tag.find_next_sibling()
            if value:
                value = cleanString(value.text)
                if value and tag.text:
                    data[tag.text] = value
    except Exception as e:
        printUnplannedError(e)

#takes a long string from a table with headers and rows and then makes a nested object and returns it
def tabularStrategy(data, field, tables, orderedFields):
    try:
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

        data[field] = tabular
    except Exception as e:
        printUnplannedError(e)

def unnamedBoldedTableStrategy(data, field, rows):
    try:
        res = []
        titles = []
        for row in rows[0].find_all("td"):
            titles.append(row.text)
    
        rows = rows[1:]
        for row in rows:
            i = 0
            obj = {}
            for val in row:
                val = cleanString(val.text)
                if val:
                    obj[titles[i]] = val

                i+=1

            res.append(obj)

        data[field] = res
    except Exception as e:
        printUnplannedError(e)

def attachData(data, field, value):
    try:
        value = cleanString(value)
        if field and value:
            data[field] = value
    except Exception as e:
        printUnplannedError(e)

#this takes the account data and attaches it to the data object passed in
def getAccountData(id):
    data = {}
    params = {"id":makeId(id)}
    print(f"url: {makeURL(Data.ACCOUNT, params)}")
    html = makeCurlFor(Data.ACCOUNT, params)
    soup = goldilocks(BeautifulSoup(html, "html.parser"))

    rows = soup.find_all("tr")

    #does re writing temp cause page misses in cashe?
    temp = rows[3].find_all("b")
    attachData(data, "Real Estate ID", temp[0].text)
    attachData(data, "PIN #", temp[1].text)

    temp = rows[7].find_all("b")
    attachData(data, "Location Address", temp[0].text)
    attachData(data, "Property Description", temp[1].text)

    temp = rows[11].find("b")
    attachData(data, "Property Owner", temp.text)

    temp = rows[9].find_all("b")
    # i think using clean string once and then three strips is faster then clean string twice with one strip. not sure though
    attachData(data, "Owner's Mailing Address", f"{temp[2].text.strip()} {temp[3].text.strip()}")
    attachData(data, "Property Location Address", f"{temp[5].text.strip()} {temp[6].text.strip()}")

    temp = rows[22].find_all("tr")
    boldStrategy(data, temp)

    return data

#this gets the data about the building
def getBuildingData(id):
    data = {}
    params = {
        "id": makeId(id),
        "cd": "01"
    }
    print(f"url: {makeURL(Data.BUILDING, params)}")
    html = makeCurlFor(Data.BUILDING, params)
    soup = goldilocks(BeautifulSoup(html, "html.parser"))

    rows = soup.find_all("tr")

    temp = rows[7].find_all("td")
    attachData(data, "Building Location Address", temp[3].text)
    attachData(data, "Building Description", temp[8].text)

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
    #TODO this fails to get the field Card 01 Value since the dang field is bold :angry:
    boldStrategy(data, temp)

    #table row with 2 col
    temp = rows[50].find("td").find_all("tr")[1:]
    tabularStrategy(data, "Main and Addition Summary", temp, ["Story", None, "Type", "Code", "Area", "Inc"])
    #can just remove the end since there is one more unwanted row always
    temp = rows[61:len(rows) - 1]
    unnamedBoldedTableStrategy(data, "Other Improvements", temp)

    return data

def getLandData(id):
    data={}
    params = {
        "id": makeId(id),
        "cd": "01"
    }
    print(f"url: {makeURL(Data.LAND, params)}")
    html = makeCurlFor(Data.LAND, params)
    soup = goldilocks(BeautifulSoup(html, "html.parser"))

    rows = soup.find_all("tr")
    temp = rows[9].find_all("td")

    attachData(data, "Land Class", temp[2].text)
    attachData(data, "Soil Class", temp[5].text)
    attachData(data, "Deeded Acres", temp[9].text)
    attachData(data, "Calculated Acres", temp[12].text)
    attachData(data, "Farm Use Year", temp[16].text)
    attachData(data, "Farm Use Flag", temp[19].text)

    temp = [rows[17]] + rows[19:len(rows) - 5]
    unnamedBoldedTableStrategy(data, "Land Value Detail - Market", temp)

    temp = rows[16].find_all("td")
    attachData(data, "Total Land Value Assessed", temp[len(temp)-1].text)

    return data

def getDeedData(id):
    data={}
    params = {
        "id": makeId(id),
        "cd": "01"
    }
    print(f"url: {makeURL(Data.DEEDS, params)}")
    html = makeCurlFor(Data.DEEDS, params)
    soup = goldilocks(BeautifulSoup(html, "html.parser"))

    rows = soup.find_all("tr")
    temp = rows[10:len(rows)-3]
    
    nobadchar = str(temp[0]).replace(" ", "historical order")
    temp[0] = BeautifulSoup(nobadchar, "html.parser")
    del temp[1::2]
    unnamedBoldedTableStrategy(data, "temp", temp)
    try:
        return [data["temp"]]
    except Exception as e:
        printUnplannedError(e)
        return []

def getNotesData(id):
    data={}
    params = {
        "id": makeId(id),
        "cd": "01"
    }
    print(f"url: {makeURL(Data.NOTES, params)}")
    html = makeCurlFor(Data.NOTES, params)
    soup = goldilocks(BeautifulSoup(html, "html.parser"))

    rows = soup.find_all("tr")

    temp = rows[12:len(rows)-3]
    unnamedBoldedTableStrategy(data, "temp", temp)
    try:
        return [data["temp"]]
    except Exception as e:
        printUnplannedError(e)
        return []

def getSalesData(id):
    data={}
    params = {
        "id": makeId(id),
        "cd": "01"
    }
    print(f"url: {makeURL(Data.SALES, params)}")
    html = makeCurlFor(Data.SALES, params)
    soup = goldilocks(BeautifulSoup(html, "html.parser"))

    rows = soup.find_all("tr")
    temp = rows[12 :len(rows) - 4]
    unnamedBoldedTableStrategy(data, "temp", temp)

    try:
        return [data["temp"]]
    except Exception as e:
        printUnplannedError(e)
        return []

#this gets all the data associated with the id and returns it
def getData(id):
    data = {}
    data[Data.ACCOUNT.value] = getAccountData(id)
    data[Data.BUILDING.value] = getBuildingData(id)
    data[Data.LAND.value] = getLandData(id)
    data[Data.DEEDS.value] = getDeedData(id)
    data[Data.NOTES.value] = getNotesData(id)
    data[Data.SALES.value] = getSalesData(id)
    return data

#this takes the data and saves it
def saveData(data, filename=None):
    if filename:
        id = filename
    else:
        id = data["Real Estate ID"]

    if not id:
        raise Exception("FAIL: id did not exist")
    
    file = open(f"{STORAGE_DIR}/{filename}.json", "w")
    file.write(json.dumps(data, indent=2))
    file.close()

def mergeFiles():
    data = []
    # Set the directory containing the JSON files

    print("Starting to merge all files...")
    # Loop through all the files in the directory
    for filename in os.listdir(STORAGE_DIR):
        # Check that the file is a JSON file
        if filename.endswith(".json"):
            # Read the JSON data from the file
            with open(os.path.join(STORAGE_DIR, filename)) as f:
                json_data = json.load(f)
                # Add the JSON data to the master array
                data.append(json_data)

    # Write the master array to a file
    saveData(data, "dump")
    print("done.")

def main():
    global FAIL_COUNT
    for id in range(1, 9999999):
        if FAIL_COUNT >= MAX_FAIL:
            print("Finished collecting data from wake county houses into private files")
            mergeFiles()
            return

        try:
            print(f"#{makeId(id)}")
            data = getData(id)
            print(data)
            saveData(data)
            FAIL_COUNT = 0
        except Exception as e:
            print(e)
            FAIL_COUNT += 1

        print("\n")

if __name__ == "__main__":
    main()
