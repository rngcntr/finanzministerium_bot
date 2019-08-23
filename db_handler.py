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
        user.tag = result[0][0].decode()
        user.full_name = result[0][1].decode()
        user.chat_id = result[0][2]
        return user
    else:
        return None

def get_status (user_a):
    cursor.execute("SELECT user_b, value FROM relative_finance WHERE user_a=%s AND NOT value=0 "
            "UNION SELECT user_a AS user_b, -value FROM relative_finance WHERE user_b=%s AND NOT value=0",
            (user_a, user_a))
    result = cursor.fetchall();
    return [RelativeFinance(userB = entry[0].decode(), value=Decimal(entry[1].decode()))  for entry in result]

def get_relative_finance (user_a, user_b):
    if user_a == user_b:
        return Decimal(0)

    switched = False
    if (user_a > user_b):
        # switch users and invert value
        tmp = user_a
        user_a = user_b
        user_b = tmp
        switched = True

    cursor.execute("SELECT value FROM relative_finance WHERE user_a=%s AND user_b=%s;",
            (user_a, user_b))
    result = cursor.fetchall();

    if len(result) > 0:
        if switched:
            return Decimal(-1) * Decimal(result[0][0].decode())
        else:
            return Decimal(result[0][0].decode())
    else:
        # insert new entry
        cursor.execute("INSERT INTO relative_finance (user_a, user_b, value) VALUES (%s, %s, %s)",
                (user_a, user_b, str(Decimal(0))))
        finanzministerium.commit()
        return Decimal(0)

def add_simple_expense (expense):
    if expense.userA == expense.userB:
        return

    # user b owes user a value units
    if (expense.userA > expense.userB):
        # switch users and invert value
        old_value = get_relative_finance(expense.userB, expense.userA)
        new_value = old_value + expense.value

        cursor.execute("UPDATE relative_finance SET value=%s WHERE user_a=%s AND user_b=%s;",
                (new_value, expense.userB, expense.userA))
        finanzministerium.commit()
    else:
        # users are in correct order
        old_value = get_relative_finance(expense.userA, expense.userB)
        new_value = old_value - expense.value

        cursor.execute("UPDATE relative_finance SET value=%s WHERE user_a=%s AND user_b=%s;",
                (new_value, expense.userA, expense.userB))
        finanzministerium.commit()

def add_expense (expense, user_a):
    for expense in expense.to_expense_list(user_a):
        add_simple_expense(expense)
