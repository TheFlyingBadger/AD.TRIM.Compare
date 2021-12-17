from functions import *
from version import getVersion
from pathlib import Path
from dataclasses import dataclass, field
import csv
from datetime import datetime
from dataclass_csv import DataclassWriter, DataclassReader, dateformat


@dataclass
class DataClassTRIM:
    name: str = None
    login: str = None
    ra: str = None
    originalRow: int = -1


@dataclass
class DataClassRA:
    name: str = None
    ra: str = None


@dataclass
@dateformat('%d/%m/%Y')
class activeAD:
    login: str
    surname: str
    firstName: str
    dateStart: datetime
    dateContractExpiry:  datetime = None
    dateTerminate:  datetime = None
    directorate: str = None
    division: str = None
    branch: str = None
    section: str = None
    RA_String: str = None
    RA: str = None
    RA_source: str = None
    originalRow: int = -1


def processTRIMCSV(theFile: Path, processedFile: Path, errorFile: Path):
    # ic(theFile)
    csvData = theFile.read_text().split('\n')
    # ic(type(csvData))
    # ic(len(csvData))
    thisRA = None
    dataLines = []
    for rownum, l in enumerate(csvData):

        if thisRA is None:
            start = l.rfind(' RA')
            if start == -1:
                start = l.rfind(',RA')
            if start == -1:
                raise Exception(f'String not found : \"{l}\"')
            thisRA = l[start:].strip(', ')
            thisRA = (f"000{thisRA[2:]}")[-3:]
            # ic(f"{l} = \"{thisRA}\"")
        elif l == ",":
            thisRA = None
        else:  # A non header row
            dataLines.append(f"{l},{thisRA},{rownum}")
            # theLine = l.strip(', ')
            # if not theLine or theLine.lower() == "None" or "," not in theLine:
            #     continue  # Bail for this row
            # thisOne = DataClassTRIM(
            #     name=lineParts[0], login=lineParts[1].lower(), ra=thisRA)
            # ic(thisOne)
            # allTRIM.append(thisOne)
    # ic(len(dataLines))
    # ic(dataLines[0:6])

    linereader = csv.reader(dataLines, delimiter=',', quotechar='"')
    allTRIM = []
    errors = []
    for line in linereader:
        # print(line)
        if len(line) != 4:
            reject = True
            thisOne = DataClassTRIM()
        else:
            thisOne = DataClassTRIM(name=line[0].strip(
                '"'), login=line[1].upper(), ra=line[2], originalRow=int(line[3]))

            reject = not thisOne.name or not thisOne.login or not thisOne.ra

            # change employee numbers to the E1nnnnnn format
            if not reject and thisOne.login and thisOne.login[0] == "E" and len(thisOne.login) <= 6:
                thisOne.login = f"E1{'0'*(6-len(thisOne.login))}{thisOne.login[1:]}"

        if reject:
            if not thisOne.name or thisOne.name.lower() == 'none':
                pass
            else:
                errors.append("\t".join(line))
        else:
            allTRIM.append(thisOne)
            # if thisOne.originalRow < 50:
            #     ic(thisOne)
        thisOne = None
        # raise Exception
    with open(processedFile, "w") as f:
        w = DataclassWriter(f, allTRIM, DataClassTRIM,
                            lineterminator="\n", delimiter="\t")
        w.write()
    if len(errors) == 0:
        errorFile.unlink(missing_ok=True)
    else:
        errorFile.write_text('\n'.join(errors))


def processADList(staffList: Path, processedFile: Path, raList: Path):

    adRows = []
    allRA = {}

    with open(staffList) as f:
        reader = DataclassReader(f, activeAD, delimiter="\t")
        reader.map('Number').to('login')
        reader.map('Surname').to('surname')
        reader.map('First Name').to('firstName')
        reader.map('Start Date').to('dateStart')
        reader.map('Contract Expiry Date').to('dateContractExpiry')
        reader.map('Terminate Date').to('dateTerminate')
        reader.map('Directorate').to('directorate')
        reader.map('Division').to('division')
        reader.map('Branch').to('branch')
        reader.map('Section').to('section')
        reader.map('RA').to('RA_String')

        suffixes = [[s, len(s)]
                    for s in [' Region', ' Directorate', ' Branch', ' Section']]

        for ix, row in enumerate(reader):
            row.originalRow = ix
            if row.RA_String:
                splitUp = row.RA_String.split(' ')
                try:
                    _ = int(splitUp[0])
                    row.RA = splitUp[0]
                    row.RA_Source = "RA"

                    # Collect the all the RAs that are defined
                    row.RA_String = ' '.join(splitUp[1:])
                    # if row.RA not in allRA:
                    #     allRA[row.RA] = raName

                    if row.RA_String not in allRA:
                        allRA[row.RA_String] = row.RA

                    for s in suffixes:

                        if row.RA_String[(-1*s[1]):] == s[0]:
                            suff = row.RA_String[:(-1*s[1])]
                            if suff not in allRA:
                                allRA[suff] = row.RA

                except:
                    pass
            adRows.append(row)

    moreRA = {}
    for r in allRA.keys():
        if '&' in r:
            newKey = r.replace('&', 'and')
            # ic(f"{r} -> {newKey}")
            moreRA[newKey] = allRA[r]
        if ' and ' in r:
            newKey = r.replace(' and ', ' & ')
            # ic(f"{r} -> {newKey}")
            moreRA[newKey] = allRA[r]

    for r in moreRA.keys():
        allRA[r] = moreRA[r]

    # ic(allRA)

    def tryTheRA(theString: str, theSource: str):
        theRA = None
        if theString:
            if theString in allRA:
                theRA = allRA[theString]
            else:
                for s in suffixes:
                    check = f"{theString}{s[0]}"
                    if check in allRA:
                        theRA = allRA[check]
                        break
                    if theString[(-1*s[1]):] == s[0]:
                        check = theString[:(-1*s[1])]
                        if check in allRA:
                            theRA = allRA[check]
                            break

        return (theRA, None if not theRA else theSource)

    for r in adRows:
        if not r.RA:
            r.RA, r.RA_Source = tryTheRA(r.RA_String, 'RA')
            if r.RA_Source:
                continue
            r.RA, r.RA_Source = tryTheRA(r.section, 'Section')
            if r.RA_Source:
                continue
            r.RA, r.RA_Source = tryTheRA(r.branch, 'Branch')
            if r.RA_Source:
                continue
            r.RA, r.RA_Source = tryTheRA(r.division, 'Division')
            if r.RA_Source:
                continue
            r.RA, r.RA_Source = tryTheRA(r.directorate, 'Directorate')
            if r.RA_Source:
                continue

    allRAs = [DataClassRA(r, allRA[r]) for r in allRA.keys()]

    with open(raList, "w") as f:
        w = DataclassWriter(f, allRAs, DataClassRA,
                            lineterminator="\n", delimiter="\t")
        w.write()

    with open(processedFile, "w") as f:
        w = DataclassWriter(f, adRows, activeAD,
                            lineterminator="\n", delimiter="\t")
        w.write()


if __name__ == '__main__':

    CONFIG = getConfig(Path('__file__').parent.parent.joinpath('config.yaml'))
    ic(getVersion())

    TRIMcsvFile = Path(CONFIG.get('FILES/TRIMCSV'))
    TRIMcsvFileProcessed = Path(CONFIG.get('FILES/TRIMCSVPROCESSED'))
    TRIMcsvFileErrors = Path(CONFIG.get('FILES/TRIMCSVERRORS'))
    processTRIMCSV(TRIMcsvFile, TRIMcsvFileProcessed, TRIMcsvFileErrors)

    activeStaffList = Path(CONFIG.get('FILES/ADSTAFFLIST'))
    activeStaffListProcessed = Path(CONFIG.get('FILES/ADSTAFFLISTPROCESSED'))
    raList = Path(CONFIG.get('FILES/RALIST'))
    processADList(activeStaffList, activeStaffListProcessed, raList)
