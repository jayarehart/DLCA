# File to scrape the HTML of EnergyPlus runs to

from dataclasses import dataclass
from eppy.results import readhtml
from eppy.results import fasthtml
from bs4 import BeautifulSoup
import os
import glob
import pandas as pd

# All the data to be collected
@dataclass
class DOEResBldgData:
    bldg_name: str
    heating_system: str
    climate_zone: str
    bldg_area: float
    electricity_kBtu: float
    naturalgas_kBtu: float
    fueloilno2_kBtu: float
    # bldg_area_units: str


# Funciton to get the list of files in a director
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
def scrape_DOERes_html(file_name:str) -> DOEResBldgData:
    # Load in the file
    # file_name = "/Users/josepharehart/Desktop/DOE_PrototypeBldgs/resstd_CZ4A_IECC_2021/US+MF+CZ4A+elecres+crawlspace+IECC_2021.table.htm"
    # filehandle = open(file_name, 'r').read
    # filehandle2 = open(file_name, 'r')
    soup = BeautifulSoup(open(file_name, 'r'), 'html.parser')

    # Get building information
    bldg_long = soup.find_all("p")[3].get_text()
    bldg_split = bldg_long.split('+')
    bldg_name = bldg_split[1] + '_' + bldg_split[4].upper()
    heating_system = bldg_split[3].upper()
    climate_zone = '_' + bldg_split[2].split('CZ')[1]

    # Scrape all the tables
    filehandle = open(file_name, 'r').read()
    htables = readhtml.titletable(filehandle)  # reads the tables with their titles

    # Get info from area table
    table_building_area = htables[2]
    bldg_area_units = table_building_area[1][0][1].split('[')[1].split(']')[0]
    bldg_area_ft2 = table_building_area[1][1][1]

    # Get info from end use table
    table_end_uses = htables[3]
    bldg_electricity_kbtu = table_end_uses[1][-1][1]
    bldg_naturalgas_kbtu = table_end_uses[1][-1][2]
    bldg_fueloil_kbtu = table_end_uses[1][-1][7]

    # Write results to DOEBldg object
    DOEBldg_i = DOEResBldgData(bldg_name=bldg_name,
                               climate_zone=climate_zone,
                               bldg_area=bldg_area_ft2,
                               # bldg_area_units=bldg_area_units,
                               electricity_kBtu=bldg_electricity_kbtu,
                               naturalgas_kBtu=bldg_naturalgas_kbtu,
                               fueloilno2_kBtu=bldg_fueloil_kbtu,
                               heating_system=heating_system)
    # DOEBldg_i.bldg_name = bldg_name
    # DOEBldg_i.climate_zone = climate_zone
    # DOEBldg_i.electricity_kBtu = table_end_uses[1][-1][1]
    # DOEBldg_i.naturalgas_kBtu = table_end_uses[1][-1][2]
    # DOEBldg_i.fueloilno2_kBtu = table_end_uses[1][-1][7]
    # DOEBldg_i.heating_system = heating_system

    return DOEBldg_i

# Get the directory name
dir_name = "/Users/josepharehart/Desktop/html_res/"
list_of_names = getListOfFiles(dir_name)

# Loop through files and get the result!
result_list = list()
for index, file in enumerate(list_of_names[0:5]):
    print(str(index) + '/' + str(len(list_of_names)) + '....' + file)
    result_scrape = scrape_DOERes_html(file)
    result_list.append(result_scrape)
result_df = pd.DataFrame([i.__dict__ for i in result_list])
result_df.to_csv("/Users/josepharehart/Desktop/html_res/_summary.csv")

