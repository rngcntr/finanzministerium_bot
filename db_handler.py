from file_handler import *

from jinja2 import Environment, FileSystemLoader
import mysql.connector
from decimal import Decimal

dbconfig_dict = load_dict("dbconfig.json");
finanzministerium = {}
cursor = {}

def initialize_database ():
    global finanzministerium
    global cursor

    dbconfig_dict = load_dict("dbconfig.json");
    finanzministerium = mysql.connector.connect(
            host = dbconfig_dict["host"],
            user = dbconfig_dict["user"],
            passwd = dbconfig_dict["passwd"],
            database = dbconfig_dict["database"])
    cursor = finanzministerium.cursor()

def add_user (tag, full_name, chat_id):
    cursor.execute("INSERT INTO users (tag, full_name, chat_id) VALUES (%s, %s, %s)",
            (tag, full_name, str(chat_id)))

def get_user_name (tag):
    cursor.execute("SELECT full_name from users WHERE tag=%s",
            tag)
    result = cursor.fetchall();
    if result:
        return result[0]
    else:
        return None

def get_user_chat (tag):
    cursor.execute("SELECT chat_id from users WHERE tag=%s",
            tag)
    result = cursor.fetchall();
    if result:
        return result[0]
    else:
        return None

def get_relative_finance (user_a, user_b):
    if (user_a > user_b):
        # switch users and invert value
        tmp = user_a
        user_a = user_b
        user_b = tmp

    result = cursor.execute("SELECT value FROM relative_finance WHERE user_a=%s AND user_b=%s",
            (user_a, user_b))
    if result:
        return Decimal(result[0])
    else:
        return Decimal(0)

def add_expense (user_a, user_b, value):
    # user b owes user a value units
    if (user_a > user_b):
        # switch users and invert value
        tmp = user_a
        user_a = user_b
        user_b = tmp
        value = -value

    old_value = get_relative_finance(user_a, user_b)
    new_value = old_value - value

    cursor.execute("INSERT INTO relative_finance (user_a, user_b, value) VALUES (%s, %s, %s)",
            (user_a, user_b, new_value))
