from agents import function_tool


@function_tool
def calculator(
    a: float,
    b: float,
    operation: str
) -> float:
    """
    Perform a mathematical calculation.

    Args:
        a: First number.
        b: Second number.
        operation: add, subtract, multiply, or divide.
    """

    if operation == "add":
        return a + b

    if operation == "subtract":
        return a - b

    if operation == "multiply":
        return a * b

    if operation == "divide":
        if b == 0:
            return 0

        return a / b

    return 0
