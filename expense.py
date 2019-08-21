from json import JSONEncoder, JSONDecoder
from decimal import Decimal
import json
import re

class Expense:
    # expense between two users
    user_a = None
    user_b = None
    reason = None
    value = None

class ComplexExpense:
    # expense between multiple users
    users = []
    reason = None
    value = None

    def from_text (complex_expense_string):
        pattern = re.compile(r"""\s*
                                (?P<value>\-?\d*\.?\d*) # value
                                \s+
                                (?P<user>\@[^\s]*(\s+\@[^\s]*)*)  # accounted user(s)
                                \s+
                                (?P<reason>[^\@.]*) # reason
                                """, re.VERBOSE)
        match = pattern.match(complex_expense_string)

        current_complex_expense = ComplexExpense()
        current_complex_expense.value = Decimal(match.group("value"))
        current_complex_expense.users = match.group("user").replace("\s*", " ").split(" ")
        current_complex_expense.users = [user.replace("@", "") for user in current_complex_expense.users]
        current_complex_expense.reason = match.group("reason")

        return current_complex_expense

    def to_expense_list (self, user_a):
        expenses = []
        for user_b in self.users:
            # don't add self-expenses
            if user_b != user_a:
                expense = Expense()
                # set attributes
                expense.user_a = user_a
                expense.user_b = user_b
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

class ComplexExpenseEncoder(JSONEncoder):
    def default(self, o):
        if (isinstance(o, Decimal)):
            return str(o)
        else:
            return o.__dict__

class ExpenseDecoder(JSONDecoder):
    def from_json(json_object):
        input_expense = Expense();
        if "user_a" in json_object:
            input_expense.user_a = json_object["user_a"]
        if "user_b" in json_object:
            input_expense.user_b = json_object["user_b"]
        if "reason" in json_object:
            input_expense.reason = json_object["reason"]
        if "value" in json_object:
            input_expense.value = Decimal(json_object["value"])

class ComplexExpenseDecoder(JSONDecoder):
    def from_json(json_object):
        input_expense = Expense();
        if "users" in json_object:
            input_expense.users = json_object["users"]
        if "reason" in json_object:
            input_expense.reason = json_object["reason"]
        if "value" in json_object:
            input_expense.value = Decimal(json_object["value"])
