#!/usr/bin/python3
import os  # Create and organize folders

from PIL import Image, ImageDraw, ImageFont  # Importing PILLOW

# Adding Airlines
######################################
# Function to create the plotlib
#####################################
from data_analysis.pandas_matplotlib import (
    plot_from_to_airport,
    plot_tunisair_arrival_dep_delays,
)
from data_pipeline.sql_functions import SqlManager
from src.const import (
    AIRLINE_NAMES,
    FLIGHT_STATUS,
    FONT_SIZE,
    SQL_OPERATORS,
    SQL_TABLE_NAME,
    TYPE_FLIGHTS,
)
from src.utils import (
    GLYPH_AIRPORT,
    SKYFONT,
    SKYFONT_INVERTED,
    FileFolderManager,
    TimeAttribute,
    is_blank,
)


def get_text_dimensions(text_string: str, font):
    """
    will return the dimensions in pixels of the text
    Args:
        text_string (str): the text string that will be outputted
        font (ImageFont): the font used for the text

    :returns:
        _type_: text_width and text_height
    """
    # https://stackoverflow.com/a/46220683/9263761
    ascent, descent = font.getmetrics()

    text_width = font.getmask(text_string).getbbox()[2]
    text_height = font.getmask(text_string).getbbox()[3] + descent

    return (text_width, text_height)


def add_banner(report, x, y, label: str, value):
    """
    Function to create the label and it's value
    the label will be in orange
    the value will be in white
    Args:
        report (ImageDraw): the report image pillow
        x (_type_): the x position
        y (_type_): the y position
        label (str): the label string will be in orange
        value (_type_): the value of the label will be in white

    :returns:
        _type_: the image updated with the new Banner LABEL : VALUE
    """

    report.text(
        (x + 10, y),
        label,
        font=ImageFont.truetype(SKYFONT_INVERTED, FONT_SIZE),
        fill="black",
    )
    width_text, height_text = get_text_dimensions(
        label, ImageFont.truetype(SKYFONT_INVERTED, FONT_SIZE)
    )
    report.text(
        (x + width_text + 10, y),
        str(value),
        font=ImageFont.truetype(SKYFONT, FONT_SIZE),
        fill="white",
    )
    report.text(
        (x + 10, y),
        label,
        font=ImageFont.truetype(SKYFONT, FONT_SIZE),
        fill="orange",
    )

    return get_text_dimensions(
        f"{label} {value}", ImageFont.truetype(SKYFONT, FONT_SIZE)
    )


def paste_plots(reportImg, x, y, plot_pic: str):
    """
    to past plots from matplotlib to the report
    Args:
        report (Image): he report from PILLOW
        x (_type_): position in x
        y (_type_): position in y
        plot_pic (str): the path of the plot picture generated by Matplotlib

    :returns:
        _type_: the image with the plot picture generated by matplotlib pasted
    """
    with Image.open(plot_pic) as plot_img:
        reportImg.paste(plot_img, (x, y))
    os.remove(plot_pic)
    return reportImg


def paste_kpi(
    report, v_start_arr, v_start_dep, v_start, h_start, query_date_formatted
):
    """
    to create 2 rounded blocks and insert KPI ,
    Count Min Max AVG per Departure Arrival

    Args:
        report (_type_): the report from PILLOW
        v_start_arr (_type_): position in x for arrival
        v_start_dep (_type_): position in x for departure
        v_start (_type_): global x pos
        h_start (_type_): global y pos
        query_date_formatted (_type_): query date formatted DD/MM/YYYY

    :returns:
        _type_: the image updated with relevant count, MIN, MAX AVG KPI
    """
    sql_table = SqlManager()
    for rounded_start in [v_start_arr, v_start_dep]:
        report.rounded_rectangle(
            (rounded_start, h_start + 35, rounded_start + 480, h_start + 115),
            radius=20,
            outline="orange",
        )

    for type_f in TYPE_FLIGHTS:
        h_start_bytype = h_start + 45
        v_start = (v_start_dep if type_f == "DEPARTURE" else v_start_arr) + 50

        # Counting how many delays
        count_nb = sql_table.execute_sql(
            f"""
            SELECT COUNT(*) 
            FROM {SQL_TABLE_NAME} 
            WHERE (
                (DEPARTURE_DATE = "{str(query_date_formatted)}") AND 
                (AIRLINE = "TU") AND 
                ({type_f}_DELAY <> "0") AND 
                ({type_f}_DELAY <> "") AND 
                (FLIGHT_STATUS <> "cancelled")
            )
            """,
            "fetchone",
        )[0]
        if type_f == "ARRIVAL":
            nb_delays_arr = count_nb
        elif type_f == "DEPARTURE":
            nb_delays_dep = count_nb
        width_text, height_text = add_banner(
            report,
            v_start + 30,
            h_start_bytype,
            f"DELAYED {type_f}:",
            f"{count_nb}",
        )
        h_start_bytype = h_start + 85

        # add more info on MIN MAX AVG
        for sql_op in SQL_OPERATORS:
            sql_execute_query = sql_table.execute_sql(
                f"""
                SELECT {sql_op}({type_f}_DELAY) 
                FROM {SQL_TABLE_NAME} 
                WHERE (
                    (DEPARTURE_DATE = "{str(query_date_formatted)}") AND 
                    (AIRLINE = "TU") AND 
                    ({type_f}_DELAY <> "0") AND 
                    ({type_f}_DELAY <> "") AND 
                    (FLIGHT_STATUS <> "cancelled")
                )
                """,
                "fetchone",
            )[0]
            result_fetch = int(
                0
                if (
                    ((sql_execute_query is None))
                    | (is_blank(sql_execute_query))
                )
                else sql_execute_query
            )
            result_fetch = int(round(result_fetch, 0))
            if (sql_op == "MAX") & (type_f == "ARRIVAL"):
                max_arrival_delay = result_fetch
            width_text, height_text = add_banner(
                report,
                v_start,
                h_start_bytype,
                f"{sql_op}:",
                f"{result_fetch}M",
            )
            v_start = v_start + width_text
    return v_start, h_start, max_arrival_delay, nb_delays_arr, nb_delays_dep


def past_worse_flight(
    report, max_arrival_delay, h_start, query_date_formatted: str
):
    """
    Args:
        report (_type_): the report from PILLOW
        max_arrival_delay (_type_): the max queried arrival delay
        h_start (_type_):  global y pos
        query_date_formatted (str): query date formatted DD/MM/YYYY

    :returns:
        _type_: the image updated with the worse flight made by Tunisair
    """
    sql_table = SqlManager()
    worse_flight = (
        []
        if max_arrival_delay == 0
        else sql_table.execute_sql(
            f"""
            SELECT 
                DEPARTURE_AIRPORT, 
                ARRIVAL_AIRPORT, 
                FLIGHT_NUMBER, 
                AIRLINE 
            FROM {SQL_TABLE_NAME}  
            WHERE (
                (DEPARTURE_DATE = "{query_date_formatted}") AND
                (AIRLINE = "TU") AND 
                (ARRIVAL_DELAY = "{str(max_arrival_delay)}") AND 
                (FLIGHT_STATUS <> "cancelled")
            )
            """,
            "fetchone",
        )
    )

    h_worse_flight = h_start + 125
    return (
        draw_with_max_arrival(
            worse_flight, report, h_worse_flight, max_arrival_delay
        )
        if max_arrival_delay > 0
        else draw_with_no_max_arrival(report, h_worse_flight)
    )


def draw_with_no_max_arrival(report, h_worse_flight):
    width_label, height_label = get_text_dimensions(
        "ALL FLIGHTS ARE ON TIME",
        ImageFont.truetype(SKYFONT, FONT_SIZE),
    )

    add_banner(
        report,
        (1080 - width_label) / 2,
        h_worse_flight,
        "ALL FLIGHTS ARE ON TIME",
        "",
    )

    result = "----------"
    width_text, height_text = get_text_dimensions(
        result, ImageFont.truetype(SKYFONT, FONT_SIZE)
    )

    position_relative = (1080 - width_text) / 2
    report.text(
        (position_relative, h_worse_flight + height_label + 10),
        result,
        font=ImageFont.truetype(SKYFONT, FONT_SIZE),
        fill="white",
    )

    return result


def draw_with_max_arrival(
    worse_flight, report, h_worse_flight, max_arrival_delay
):
    airport_worse_dep = worse_flight[0]
    airport_worse_arr = worse_flight[1]
    worse_flight_number = worse_flight[2]
    worse_airline = AIRLINE_NAMES[worse_flight[3]]
    width_label, height_label = get_text_dimensions(
        f"WORST FLIGHT: {worse_airline} {worse_flight_number}",
        ImageFont.truetype(SKYFONT, 20),
    )

    add_banner(
        report,
        (1080 - width_label) / 2,
        h_worse_flight,
        "WORST FLIGHT:",
        f"{worse_airline} {worse_flight_number}",
    )

    result = str(
        f"{airport_worse_dep} -----Delay of {str(max_arrival_delay)}M----> {airport_worse_arr}"
    )

    width_text, height_text = get_text_dimensions(
        result, ImageFont.truetype(SKYFONT, FONT_SIZE)
    )

    position_relative = (1080 - width_text) / 2
    report.text(
        (position_relative - 40, h_worse_flight + height_label + 15),
        "Q",
        font=ImageFont.truetype(GLYPH_AIRPORT, FONT_SIZE),
        fill="white",
    )

    report.text(
        (position_relative, h_worse_flight + height_label + 15),
        result,
        font=ImageFont.truetype(SKYFONT, FONT_SIZE),
        fill="white",
    )

    report.text(
        (
            position_relative + width_text + 10,
            h_worse_flight + height_label + 15,
        ),
        "P",
        font=ImageFont.truetype(GLYPH_AIRPORT, FONT_SIZE),
        fill="white",
    )

    return result


def past_titles(report, datetime_query):
    """
    To generate titles in the white AREA
    Args:
        report (_type_): the report from PILLOW
        datetime_query (_type_): query date formatted DD/MM/YYYY
    """
    # Last update hour
    report.text(
        (55, 60),
        f"LAST UPDATE AT {TimeAttribute(datetime_query).full_hour}",
        font=ImageFont.truetype(SKYFONT, 9),
        fill="black",
    )
    # Big Title
    report.text(
        (260, 10),
        f"TUNISAIR DAILY INGEST {TimeAttribute(datetime_query).full_day}",
        font=ImageFont.truetype(SKYFONT, 25),
        fill="black",
    )
    # Subtitle
    report.text(
        (260, 50),
        "SCOPE FROM/TO Tunis-Carthage International Airport",
        font=ImageFont.truetype(SKYFONT, 15),
        fill="black",
    )
    return report


def flight_status_kpi(report, query_date_formatted: str, h_start, v_start_dep):
    """
    To generate the KPI count per flight status (Scheduled, Canceled, Active, Landed)

    Args:
        report (_type_): the report from PILLOW
        query_date_formatted (str): query date formatted DD/MM/YYYY
        h_start (_type_): global y pos
        v_start_dep (_type_): position in x for departure

    :returns:
        _type_: the image updated with the KPI by flight status
    """
    sql_table = SqlManager()
    h_start = h_start + 15
    width_text, height_text = add_banner(
        report, v_start_dep, h_start, "TUNISAIR FLIGHTS", ""
    )

    v_start = v_start_dep + width_text + 10
    for status in FLIGHT_STATUS:
        count_sql_status = sql_table.execute_sql(
            f"""
            SELECT COUNT(*) 
            FROM {SQL_TABLE_NAME} 
            WHERE (
                (DEPARTURE_DATE = "{query_date_formatted}") AND 
                (AIRLINE = "TU") AND 
                (FLIGHT_STATUS = "{status}")
            )
            """,
            "fetchone",
        )[0]

        width_text, height_text = add_banner(
            report, v_start, h_start, f"{status}:", count_sql_status
        )

        v_start = v_start + width_text + 10
    return v_start, h_start


def get_picture_to_save_loc(datetime_query):
    """
    To create the dir and prepare the save of the report png
    Args:
        datetime_query (_type_): the datetime query

    :returns:
        _type_: the file path where to store the report
    """
    return FileFolderManager(
        directory=f"data_analysis/reports/{TimeAttribute(datetime_query).month}",
        name_file=f"{TimeAttribute(datetime_query).short_under_score}_report.png",
    ).file_dir


def generate_report(datetime_query):
    """
    Function to generate the daily report as function of current time
    Args:
        datetime_query (_type_): datetime

    :returns:
        _type_: the path of the report image
    """

    # Create necessary folders and paths
    query_date_formatted = TimeAttribute(datetime_query).dateformat
    picture_to_save = get_picture_to_save_loc(datetime_query)
    reportImg = Image.new("RGB", (1080, 720), color="white")

    # LOGO BLOCK
    with Image.open(
        FileFolderManager(
            directory="src", name_file="tunisair_alert_logo.png"
        ).file_dir
    ) as tunisair_logo:
        reportImg.paste(tunisair_logo, (25, 7))

    report = ImageDraw.Draw(reportImg)
    # TITLES BLOCKS
    past_titles(report, datetime_query)

    # Positions
    v_start_dep = 15  # vertical position for DEPARTURES
    v_start_arr = 580  # vertical position for ARRIVALS
    h_start = 80  # horizontal position

    # KPI BLOCKS
    report.rectangle((0, h_start, 1080, 720), fill="black")

    # To get the repartition count by flight status
    v_start, h_start = flight_status_kpi(
        report, query_date_formatted, h_start, v_start_dep
    )

    # To prepare the KPI of counting in Departure & Counting in Arrivals
    # 2 rounded rectangles that will contain the KPIs
    (
        v_start,
        h_start,
        max_arrival_delay,
        nb_delays_arr,
        nb_delays_dep,
    ) = paste_kpi(
        report, v_start_arr, v_start_dep, v_start, h_start, query_date_formatted
    )

    # Get the information of WORSE Flight
    text_worse_flight = past_worse_flight(
        report, max_arrival_delay, h_start, query_date_formatted
    )

    # PLOT BLOCKS
    paste_plots(
        reportImg,
        v_start_dep,
        290,
        plot_tunisair_arrival_dep_delays(datetime_query),
    )

    plot_h_pos = 470
    paste_plots(
        reportImg,
        v_start_dep,
        plot_h_pos,
        plot_from_to_airport(datetime_query, "DEPARTURE", "TUNISIA", "FRANCE"),
    )

    paste_plots(
        reportImg,
        530,
        plot_h_pos,
        plot_from_to_airport(datetime_query, "ARRIVAL", "FRANCE", "TUNISIA"),
    )

    report.rounded_rectangle(
        (v_start_dep, 290, 1060, 705), radius=20, outline="orange"
    )

    # SAVE PICTURE
    reportImg.save(picture_to_save)
    print(
        f"Daily report created for {TimeAttribute(datetime_query).short_under_score}"
    )
    return (
        picture_to_save,
        nb_delays_arr,
        nb_delays_dep,
        max_arrival_delay,
        text_worse_flight,
    )
