from decimal import Decimal

class RelativeFinance:
    # relative finance between the user and a single other user
    userB = None
    value = None

    def __init__(self, userB, value):
        self.userB = userB
        self.value = value
