from json import JSONEncoder, JSONDecoder
from decimal import Decimal
import json
import re

class Expense:
    # expense between two users
    userA = None
    userB = None
    reason = None
    value = None

class CompleteExpense:
    # expense between multiple users
    users = []
    reason = None
    value = None

    def from_text (complete_expense_string):
        pattern = re.compile(r"""\s*
                                (?P<value>\-?\d*\.?\d*) # value
                                \s+
                                (?P<user>\@[^\s]*(\s+\@[^\s]*)*)  # accounted user(s)
                                \s+
                                (?P<reason>[^\@.]*) # reason
                                """, re.VERBOSE)
        match = pattern.match(complete_expense_string)

        current_complete_expense = CompleteExpense()
        current_complete_expense.value = Decimal(match.group("value"))
        current_complete_expense.users = match.group("user").replace("\s*", " ").split(" ")
        current_complete_expense.reason = match.group("reason")

        return current_complete_expense

    def to_expense_list (self, userA):
        expenses = []
        for userB in self.users:
            # don't add self-expenses
            if userB != userA:
                expense = Expense()
                # set attributes
                expense.userA = userA
                expense.userB = userB
                expense.reason = self.reason
                expense.value = self.value / len(self.users)
                expenses.append(expense)
        return expenses

class ExpenseEncoder(JSONEncoder):
    def default(self, o):
        if (isinstance(o, Decimal)):
            return str(o)
        else:
            return o.__dict__

class CompleteExpenseEncoder(JSONEncoder):
    def default(self, o):
        if (isinstance(o, Decimal)):
            return str(o)
        else:
            return o.__dict__

class ExpenseDecoder(JSONDecoder):
    def from_json(json_object):
        input_expense = Expense();
        if "userA" in json_object:
            input_expense.userA = json_object["userA"]
        if "userB" in json_object:
            input_expense.userB = json_object["userB"]
        if "reason" in json_object:
            input_expense.reason = json_object["reason"]
        if "value" in json_object:
            input_expense.value = Decimal(json_object["value"])

class CompleteExpenseDecoder(JSONDecoder):
    def from_json(json_object):
        input_expense = Expense();
        if "users" in json_object:
            input_expense.users = json_object["users"]
        if "reason" in json_object:
            input_expense.reason = json_object["reason"]
        if "value" in json_object:
            input_expense.value = Decimal(json_object["value"])
