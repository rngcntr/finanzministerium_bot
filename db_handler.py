from jinja2 import Environment, FileSystemLoader
from relative_finance import *
from decimal import Decimal
from file_handler import *
import mysql.connector
from expense import *
from user import *

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
    cursor = finanzministerium.cursor(prepared=True)

def add_user (tag, full_name, chat_id):
    cursor.execute("INSERT INTO users (tag, full_name, chat_id) VALUES (%s, %s, %s);",
            (tag, full_name, str(chat_id)))
    finanzministerium.commit()

def get_user (tag):
    cursor.execute("SELECT tag, full_name, chat_id FROM users WHERE tag=%s;", (tag,))
    result = cursor.fetchall()
    if result:
        user = User()
        user.tag = result[0][0]
        user.full_name = result[0][1]
        user.chat_id = result[0][2]
        return user
    else:
        return None

def get_user_name (tag):
    cursor.execute("SELECT full_name FROM users WHERE tag=%s;", (tag,))
    result = cursor.fetchall()
    if result:
        return result[0][0]
    else:
        return None

def get_user_chat (tag):
    cursor.execute("SELECT chat_id FROM users WHERE tag=%s;", (tag,))
    result = cursor.fetchall();
    if result:
        return result[0][0]
    else:
        return None

def get_status (user_a):
    cursor.execute("SELECT user_b, value FROM relative_finance WHERE user_a=%s AND NOT value=0 "
            "UNION SELECT user_a AS user_b, -value FROM relative_finance WHERE user_b=%s AND NOT value=0",
            (user_a, user_a))
    result = cursor.fetchall();
    return [RelativeFinance(userB = entry[0], value=Decimal(entry[1]))  for entry in result]

def get_relative_finance (user_a, user_b):
    if user_a == user_b:
        return Decimal(0)

    switched = false
    if (user_a > user_b):
        # switch users and invert value
        tmp = user_a
        user_a = user_b
        user_b = tmp
        switched = true

    cursor.execute("SELECT value FROM relative_finance WHERE user_a=%s AND user_b=%s;",
            (user_a, user_b))
    result = cursor.fetchall();
    if result:
        if switched:
            return -Decimal(result[0][0])
        else:
            return Decimal(result[0][0])
    else:
        # insert new entry
        cursor.execute("INSERT INTO relative_finance (user_a, user_b, value) VALUES (%s, %s, %s)",
                (user_a, user_b, str(Decimal(0))))
        return Decimal(0)

def add_expense (expense):
    if expense.user_a == expense.user_b:
        return

    # user b owes user a value units
    if (expense.user_a > expense.user_b):
        # switch users and invert value
        tmp = expense.user_a
        expense.user_a = expense.user_b
        expense.user_b = tmp
        expense.value = -expense.value

    old_value = get_relative_finance(expense.user_a, expense.user_b)
    new_value = old_value - expense.value

    cursor.execute("UPDATE relative_finance SET value=%s WHERE user_a=%s AND user_b=%s;",
            (new_value, expense.user_a, expense.user_b))
    finanzministerium.commit()

def add_complex_expense (complex_expense, user_a):
    for expense in complex_expense.to_expense_list(user_a):
        add_expense (expense)
