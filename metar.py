#!/usr/bin/env python3
# METARMap script written by Tyler Miller and Josh Cramer

import urllib.request
import xml.etree.ElementTree as ET
import board
import neopixel
import time
import datetime
try:
    import astral
except ImportError:
    astral = None
try:
    import displaymetar
except ImportError:
    displaymetar = None

import json
import datetime


print("Running metar.py at " + datetime.datetime.now().strftime('%d/%m/%Y %H:%M'))

# Read the JSON file
with open('config.json') as f:
    config_data = json.load(f)

# NeoPixel LED Configuration
LED_COUNT = config_data['LED_COUNT']
LED_BRIGHTNESS = config_data['LED_BRIGHTNESS']
LED_PIN = board.D18
LED_ORDER = neopixel.GRB
if(config_data['LED_ORDER'] == True):
    LED_ORDER = neopixel.RGB

# Define Pixel Colors
COLOR_VFR = config_data['COLOR_VFR']
COLOR_VFR_FADE = config_data['COLOR_VFR_FADE']
COLOR_MVFR = config_data['COLOR_MVFR']
COLOR_MVFR_FADE = config_data['COLOR_MVFR_FADE']
COLOR_IFR = config_data['COLOR_IFR']
COLOR_IFR_FADE = config_data['COLOR_IFR_FADE']
COLOR_LIFR = config_data['COLOR_LIFR']
COLOR_LIFR_FADE = config_data['COLOR_LIFR_FADE']
COLOR_OFF = config_data['COLOR_OFF']
COLOR_LIGHTNING = config_data['COLOR_LIGHTNING']
COLOR_HIGH_WINDS = config_data['COLOR_HIGH_WINDS']

# Define Animation States
ACTIVATE_WINDCONDITION_ANIMATION = config_data['ACTIVATE_WINDCONDITION_ANIMATION']
ACTIVATE_LIGHTNING_ANIMATION = config_data['ACTIVATE_LIGHTNING_ANIMATION']

# Animation Parameters
MAX_LIGHTNING_BLINK_ON_TIME = config_data['MAX_LIGHTNING_BLINK_ON_TIME']
FADE_INSTEAD_OF_BLINK = config_data['FADE_INSTEAD_OF_BLINK']
WIND_BLINK_THRESHOLD = config_data['WIND_BLINK_THRESHOLD']
HIGH_WINDS_THRESHOLD = config_data['HIGH_WINDS_THRESHOLD']
ALWAYS_BLINK_FOR_GUSTS = config_data['ALWAYS_BLINK_FOR_GUSTS']
BLINK_SPEED = config_data['BLINK_SPEED']
BLINK_TOTALTIME_SECONDS = config_data['BLINK_TOTALTIME_SECONDS']
ACTIVATE_DAYTIME_DIMMING = config_data['ACTIVATE_DAYTIME_DIMMING']

# Astral timings
BRIGHT_TIME_START = datetime.datetime.strptime(config_data['BRIGHT_TIME_START'], "%H:%M").time()
DIM_TIME_START = datetime.datetime.strptime(config_data['DIM_TIME_START'], "%H:%M").time()

# Other Settings
LED_BRIGHTNESS_DIM = config_data['LED_BRIGHTNESS_DIM']
USE_SUNRISE_SUNSET = config_data['USE_SUNRISE_SUNSET']
LOCATION = config_data['LOCATION']
ACTIVATE_EXTERNAL_METAR_DISPLAY = config_data['ACTIVATE_EXTERNAL_METAR_DISPLAY']
DISPLAY_ROTATION_SPEED = config_data['DISPLAY_ROTATION_SPEED']
SHOW_LEGEND = config_data['SHOW_LEGEND']
OFFSET_LEGEND_BY = config_data['OFFSET_LEGEND_BY']

# Sunrise/Sunset across the map - needs to be fixed
def astralTimes(astral):
    if astral is None:
        return
    
    if not USE_SUNRISE_SUNSET:
        return
    
    try:
        # For older clients running python 3.5 which are using Astral 1.10.1
        ast = astral.Astral()
        try:
            city = ast[LOCATION]
        except KeyError:
            print("Error: Location not recognized, please check list of supported cities and reconfigure")
        else:
            print(city)
            sun = city.sun(date = datetime.datetime.now().date(), local = True)
            BRIGHT_TIME_START = sun['sunrise'].time()
            DIM_TIME_START = sun['sunset'].time()
    except AttributeError:
        # newer Raspberry Pi versions using Python 3.6+ using Astral 2.2
        import astral.geocoder
        import astral.sun
        try:
            city = astral.geocoder.lookup(LOCATION, astral.geocoder.database())
        except KeyError:
            print("Error: Location not recognized, please check list of supported cities and reconfigure")
        else:
            print(city)
            sun = astral.sun.sun(city.observer, date = datetime.datetime.now().date(), tzinfo=city.timezone)
            BRIGHT_TIME_START = sun['sunrise'].time()
            DIM_TIME_START = sun['sunset'].time()
    print("Sunrise:" + BRIGHT_TIME_START.strftime('%H:%M') + " Sunset:" + DIM_TIME_START.strftime('%H:%M'))

# Initialize the LED strip
def initializeLEDs():
    bright = BRIGHT_TIME_START < datetime.datetime.now().time() < DIM_TIME_START
    pixels = neopixel.NeoPixel(LED_PIN, LED_COUNT, brightness = LED_BRIGHTNESS_DIM if (ACTIVATE_DAYTIME_DIMMING and bright == False) else LED_BRIGHTNESS, pixel_order = LED_ORDER, auto_write = False)

    print("Wind animation:" + str(ACTIVATE_WINDCONDITION_ANIMATION))
    print("Lightning animation:" + str(ACTIVATE_LIGHTNING_ANIMATION))
    print("Daytime Dimming:" + str(ACTIVATE_DAYTIME_DIMMING) + (" using Sunrise/Sunset" if USE_SUNRISE_SUNSET and ACTIVATE_DAYTIME_DIMMING else ""))
    print("External Display:" + str(ACTIVATE_EXTERNAL_METAR_DISPLAY))
    
    return pixels

# Read the airports file to retrieve list of airports and use as order for LEDs
def getAirports():
    with open("/home/jcramer/airports") as f:
        airports = f.readlines()
    airports = [x.strip() for x in airports]
    try:
        with open("/home/jcramer/displayairports") as f2:
            displayairports = f2.readlines()
        displayairports = [x.strip() for x in displayairports]
        print("Using subset airports for LED display")
    except IOError:
        print("Rotating through all airports on LED display")
        displayairports = None

    if len(airports) > LED_COUNT:
        print()
        print("WARNING: Too many airports in airports file, please increase LED_COUNT or reduce the number of airports")
        print("Airports: " + str(len(airports)) + " LED_COUNT: " + str(LED_COUNT))
        print()
        quit()

    return airports, displayairports

# Retrieve METAR from aviationweather.gov data server
def getMetarData(airports):
    # Details about parameters can be found here: https://aviationweather.gov/data/api/#/Dataserver/dataserverMetars
    url = "https://aviationweather.gov/cgi-bin/data/dataserver.php?requestType=retrieve&dataSource=metars&stationString=" + ",".join([item for item in airports if item != "NULL"]) + "&hoursBeforeNow=5&format=xml&mostRecent=true&mostRecentForEachStation=constraint"
    print(url)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36 Edg/86.0.622.69'})
    content = urllib.request.urlopen(req).read()

    return content

# Retrieve flying conditions from the service response and store in a dictionary for each airport
def parseMetarData(content, displayairports):
    root = ET.fromstring(content)
    conditionDict = { "NULL": {"flightCategory" : "", "windDir": "", "windSpeed" : 0, "windGustSpeed" :  0, "windGust" : False, "lightning": False, "tempC" : 0, "dewpointC" : 0, "vis" : 0, "altimHg" : 0, "obs" : "", "skyConditions" : {}, "obsTime" : datetime.datetime.now() } }
    conditionDict.pop("NULL")
    stationList = []
    for metar in root.iter('METAR'):
        stationId = metar.find('station_id').text
        if metar.find('flight_category') is None:
            print("Missing flight condition, skipping.")
            continue
        flightCategory = metar.find('flight_category').text
        windDir = ""
        windSpeed = 0
        windGustSpeed = 0
        windGust = False
        lightning = False
        tempC = 0
        dewpointC = 0
        vis = 0
        altimHg = 0.0
        obs = ""
        skyConditions = []
        if metar.find('wind_gust_kt') is not None:
            windGustSpeed = int(metar.find('wind_gust_kt').text)
            windGust = (True if (ALWAYS_BLINK_FOR_GUSTS or windGustSpeed > WIND_BLINK_THRESHOLD) else False)
        if metar.find('wind_speed_kt') is not None:
            windSpeed = int(metar.find('wind_speed_kt').text)
        if metar.find('wind_dir_degrees') is not None:
            windDir = metar.find('wind_dir_degrees').text
        if metar.find('temp_c') is not None:
            tempC = int(round(float(metar.find('temp_c').text)))
        if metar.find('dewpoint_c') is not None:
            dewpointC = int(round(float(metar.find('dewpoint_c').text)))
        if metar.find('visibility_statute_mi') is not None:
            vis_str = metar.find('visibility_statute_mi').text
            vis_str = vis_str.replace('+', '')
            vis = int(round(float(vis_str)))
        if metar.find('altim_in_hg') is not None:
            altimHg = float(round(float(metar.find('altim_in_hg').text), 2))
        if metar.find('wx_string') is not None:
            obs = metar.find('wx_string').text
        if metar.find('observation_time') is not None:
            obsTime = datetime.datetime.fromisoformat(metar.find('observation_time').text.replace("Z","+00:00"))
        for skyIter in metar.iter("sky_condition"):
            skyCond = { "cover" : skyIter.get("sky_cover"), "cloudBaseFt": int(skyIter.get("cloud_base_ft_agl", default=0)) }
            skyConditions.append(skyCond)
        if metar.find('raw_text') is not None:
            rawText = metar.find('raw_text').text
            lightning = False if ((rawText.find('LTG', 4) == -1 and rawText.find('TS', 4) == -1) or rawText.find('TSNO', 4) != -1) else True
        print(stationId + ":" 
        + flightCategory + ":" 
        + str(windDir) + "@" + str(windSpeed) + ("G" + str(windGustSpeed) if windGust else "") + ":"
        + str(vis) + "SM:"
        + obs + ":"
        + str(tempC) + "/"
        + str(dewpointC) + ":"
        + str(altimHg) + ":"
        + str(lightning))
        conditionDict[stationId] = { "flightCategory" : flightCategory, "windDir": windDir, "windSpeed" : windSpeed, "windGustSpeed": windGustSpeed, "windGust": windGust, "vis": vis, "obs" : obs, "tempC" : tempC, "dewpointC" : dewpointC, "altimHg" : altimHg, "lightning": lightning, "skyConditions" : skyConditions, "obsTime": obsTime }
        if displayairports is None or stationId in displayairports:
            stationList.append(stationId)

    return stationList, conditionDict

# Start up external display output
def startExternalDisplay():
    disp = None
    if displaymetar is not None and ACTIVATE_EXTERNAL_METAR_DISPLAY:
        print("setting up external display")
        disp = displaymetar.startDisplay()
        displaymetar.clearScreen(disp)

    return disp

#Find the LED color for an LED's given scenario
def getLedColor(_conditions, windCycle):
    if _conditions is None:
        return COLOR_OFF, None

    windy = (ACTIVATE_WINDCONDITION_ANIMATION and windCycle and (_conditions["windSpeed"] >= WIND_BLINK_THRESHOLD or _conditions["windGust"]))
    highWinds = (windy and HIGH_WINDS_THRESHOLD != -1 and (_conditions["windSpeed"] >= HIGH_WINDS_THRESHOLD or _conditions["windGustSpeed"] >= HIGH_WINDS_THRESHOLD))
    lightningConditions = (ACTIVATE_LIGHTNING_ANIMATION and (not windCycle) and _conditions["lightning"])

    if not (windy or lightningConditions):
        if _conditions["flightCategory"] == "VFR":
            return COLOR_VFR, None
        if _conditions["flightCategory"] == "MVFR":
            return COLOR_MVFR, None
        if _conditions["flightCategory"] == "IFR":
            return COLOR_IFR, None
        if _conditions["flightCategory"] == "LIFR":
            return COLOR_LIFR, None
    
    if lightningConditions:
        if _conditions["flightCategory"] == "VFR":
            return COLOR_LIGHTNING, COLOR_VFR
        if _conditions["flightCategory"] == "MVFR":
            return COLOR_LIGHTNING, COLOR_MVFR
        if _conditions["flightCategory"] == "IFR":
            return COLOR_LIGHTNING, COLOR_IFR
        if _conditions["flightCategory"] == "LIFR":
            return COLOR_LIGHTNING, COLOR_LIFR
    
    if highWinds:
        return COLOR_HIGH_WINDS, None
    
    if windy:
        if FADE_INSTEAD_OF_BLINK:
            if _conditions["flightCategory"] == "VFR":
                return COLOR_VFR_FADE, None
            if _conditions["flightCategory"] == "MVFR":
                return COLOR_MVFR_FADE, None
            if _conditions["flightCategory"] == "IFR":
                return COLOR_IFR_FADE, None
            if _conditions["flightCategory"] == "LIFR":
                return COLOR_LIFR_FADE  , None      
        return COLOR_OFF, None
    
    return COLOR_OFF, None

#Update legend
def showLegend(pixels, windCycle, i):
    if not SHOW_LEGEND:
        return
    
    pixels[i + OFFSET_LEGEND_BY] = COLOR_VFR
    pixels[i + OFFSET_LEGEND_BY + 1] = COLOR_MVFR
    pixels[i + OFFSET_LEGEND_BY + 2] = COLOR_IFR
    pixels[i + OFFSET_LEGEND_BY + 3] = COLOR_LIFR

    if ACTIVATE_LIGHTNING_ANIMATION == True:
        pixels[i + OFFSET_LEGEND_BY + 4] = COLOR_LIGHTNING if windCycle else COLOR_VFR # lightning

    if ACTIVATE_WINDCONDITION_ANIMATION == True:
        pixels[i+ OFFSET_LEGEND_BY + 5] = COLOR_VFR if not windCycle else (COLOR_VFR_FADE if FADE_INSTEAD_OF_BLINK else COLOR_OFF)    # windy

        if HIGH_WINDS_THRESHOLD != -1:
            pixels[i + OFFSET_LEGEND_BY + 6] = COLOR_VFR if not windCycle else COLOR_HIGH_WINDS  # high winds

# Rotate through airports METAR on external display
def updateDisplay(displayTime, displayAirportCounter, disp, stationList, conditionDict, numAirports):
    if disp is None:
        return displayTime, displayAirportCounter
    
    if displayTime <= DISPLAY_ROTATION_SPEED:
        displaymetar.outputMetar(disp, stationList[displayAirportCounter], conditionDict.get(stationList[displayAirportCounter], None))
        displayTime += BLINK_SPEED
        return displayTime, displayAirportCounter

    displayTime = 0.0
    displayAirportCounter = displayAirportCounter + 1 if displayAirportCounter < numAirports-1 else 0
    print("Showing METAR Display for " + stationList[displayAirportCounter])
    return displayTime, displayAirportCounter

#Compare a list and tuple
def CompareListToTuple(litem, titem):
    return litem[0] == titem[0] and litem[1] == titem[1] and litem[2] == titem[2]

#Update lightning strobe
def UpdateLightningStrobe(airports, lightningStrobeColors, pixels):
    for i, airportcode in enumerate(airports):
        if lightningStrobeColors[i] is None:
            continue

        if CompareListToTuple(pixels[i], COLOR_LIGHTNING) == True:
            pixels[i] = lightningStrobeColors[i]
        else:
            pixels[i] = COLOR_LIGHTNING

    return pixels

# Setting LED colors based on weather conditions
def setLEDs(stationList, airports, conditionDict, pixels, disp):    
    blinksRemaining = 1
    windCycle = False
    displayTime = 0.0
    displayAirportCounter = 0
    numAirports = len(stationList)

    if ACTIVATE_WINDCONDITION_ANIMATION or ACTIVATE_LIGHTNING_ANIMATION or ACTIVATE_EXTERNAL_METAR_DISPLAY:
        blinksRemaining = int(round(BLINK_TOTALTIME_SECONDS / BLINK_SPEED))

    while blinksRemaining > 0:
        lightningStrobeColors = []

        for i, airportcode in enumerate(airports):
            if airportcode == "NULL":
                continue

            color = COLOR_OFF
            windy = False
            highWinds = False
            lightningConditions = False
            conditions = conditionDict.get(airportcode, None)
            
            color, lightningStrobeColor = getLedColor(conditions, windCycle)
            print("Setting LED " + str(i) + " for " + airportcode + " to " + ("lightning " if lightningConditions else "") + ("very " if highWinds else "") + ("windy " if windy else "") + (conditions["flightCategory"] if conditions != None else "None") + " " + str(color))
            pixels[i] = color
            if lightningStrobeColor is None:
                lightningStrobeColors.append(None)
            else:
                lightningStrobeColors.append(lightningStrobeColor)


        showLegend(pixels, windCycle, i)
        displayTime, displayAirportCounter = updateDisplay(displayTime, displayAirportCounter, disp, stationList, conditionDict, numAirports)

        #show the base colors
        pixels = UpdateLightningStrobe(airports, lightningStrobeColors, pixels)
        pixels.show()
        time.sleep((BLINK_SPEED - MAX_LIGHTNING_BLINK_ON_TIME)/2)

        #show the lightning flash
        pixels = UpdateLightningStrobe(airports, lightningStrobeColors, pixels)
        pixels.show()   
        time.sleep(MAX_LIGHTNING_BLINK_ON_TIME)

        #show remaining base colors
        pixels = UpdateLightningStrobe(airports, lightningStrobeColors, pixels)
        pixels.show()   
        time.sleep((BLINK_SPEED - MAX_LIGHTNING_BLINK_ON_TIME)/2)

        # # Update actual LEDs all at once
        # for x in range(MAX_BLINKS_OF_LIGHTNING):
        #     pixels = UpdateLightningStrobe(airports, lightningStrobeColors, pixels)
        #     pixels.show()        
        #     time.sleep(BLINK_SPEED / MAX_BLINKS_OF_LIGHTNING)


        # Switching between animation cycles
        windCycle = not windCycle
        blinksRemaining -= 1

astralTimes(astral)

pixels = initializeLEDs()

airports, displayairports = getAirports()

content = getMetarData(airports)

stationList, conditionDict = parseMetarData(content, displayairports)

disp = startExternalDisplay()

setLEDs(stationList, airports, conditionDict, pixels, disp)
