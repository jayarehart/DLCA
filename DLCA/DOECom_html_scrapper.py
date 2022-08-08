# File to scrape the HTML of EnergyPlus runs to

from dataclasses import dataclass
from eppy.results import readhtml
from eppy.results import fasthtml
from bs4 import BeautifulSoup
import os
import pandas as pd

# All the data to be collected
@dataclass
class DOEComBldgData:
    bldg_name: str
    climate_zone: str
    bldg_area: float
    electricity_GJ: float
    naturalgas_GJ: float
    bldg_area_units: str


# Function to get the list of files in a director
def getListOfFiles(dirName):
    # create a list of file and sub directories
    # names in the given directory
    listOfFile = os.listdir(dirName)
    allFiles = list()
    # Iterate over all the entries
    for entry in listOfFile:
        # Create full path
        fullPath = os.path.join(dirName, entry)
        # If entry is a directory then get the list of files in this directory
        if os.path.isdir(fullPath):
            allFiles = allFiles + getListOfFiles(fullPath)
        else:
            allFiles.append(fullPath)

    return allFiles

# Function to scrape the DOE residential building models
def scrape_DOERes_html(file_name:str) -> DOEComBldgData:
    # Load in the file
    # file_name = "/Users/josepharehart/Desktop/DOE_PrototypeBldgs/ASHRAE901_HotelLarge/ASHRAE901_HotelLarge_STD2019_Tucson.table.htm"
    soup = BeautifulSoup(open(file_name, 'r'), 'html.parser')

    # Get building information
    bldg_long = soup.find_all("p")[3].get_text()
    bldg_name = bldg_long.split(': ')[1].upper()

    matched_tags = soup.find_all(lambda tag: len(tag.find_all()) == 0 and "CLIMATEZONE" in tag.text)
    climate_zone = matched_tags[0].contents[0].split("ZONE ")[1]

    # Scrape all the tables
    filehandle = open(file_name, 'r').read()

    # Get info from area table
    filehandle2 = open(file_name, 'r')
    table_building_area = fasthtml.tablebyindex(filehandle2, 2)
    bldg_area_units = table_building_area[1][0][1].split('[')[1].split(']')[0]
    bldg_area_m2 = table_building_area[1][1][1]

    # Get info from end use table
    filehandle3 = open(file_name, 'r')
    table_end_uses = fasthtml.tablebyindex(filehandle3, 3)
    bldg_electricity_GJ = table_end_uses[1][-1][1]
    bldg_naturalgas_GJ = table_end_uses[1][-1][2]

    # Write results to DOEBldg object
    DOEBldg_i = DOEComBldgData(bldg_name=bldg_name,
                               climate_zone=climate_zone,
                               bldg_area=bldg_area_m2,
                               bldg_area_units=bldg_area_units,
                               electricity_GJ=bldg_electricity_GJ,
                               naturalgas_GJ=bldg_naturalgas_GJ
                               )

    return DOEBldg_i

# Get the directory name
dir_name = "/Users/josepharehart/Desktop/html_com/"
list_of_names = getListOfFiles(dir_name)

# Loop through files and get the result!
result_list = list()
for index, file in enumerate(list_of_names[0:5]):
    print(str(index) + '/' + str(len(list_of_names)) + '....' + file)
    result_scrape = scrape_DOERes_html(file)
    result_list.append(result_scrape)
result_df = pd.DataFrame([i.__dict__ for i in result_list])
result_df.to_csv("/Users/josepharehart/Desktop/html_com/_summary.csv")




