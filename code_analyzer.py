import json
import sys
import os
from collections import namedtuple
import re
import ast

blanklines = 0
blankline_flag = False

ResultItem = namedtuple("ResultItem", ["path", "line", "error"])

def get_input_files(path: str):

    if os.path.isfile(path):
        return [path]
    elif os.path.isdir(path):
        root, _, files = list(os.walk(path))[0]
        return [f'{root}\\{file}' for file in files]

def len_check(line: str):

    if len(line) > 79:
        return ("S001", "Too long" )

def indent_check(line: str):

    leading_spaces = len(line) - len(line.lstrip())
    if not leading_spaces or line == "\n":
        return
    elif leading_spaces % 4:
        return ("S002", "Indentation is not a multiple of four")

def semicolon_check(line: str):

    if ";" in line:
        if "#" in line:
            line = line.split("#")[0]
            if ";" in line:
                return ("S003", "Unnecessary semicolon after a statement (note that semicolons are acceptable in comments)")
        elif line.rstrip().endswith(";"):
            return ("S003", "Unnecessary semicolon after a statement (note that semicolons are acceptable in comments)")

def inline_comment_check(line: str):

    if "#" in line and line[0] != "#":
        if line.split("#")[0][-2:] != "  ":
            return ("S004", "Less than two spaces before inline comments")
    else:
        return

def todo_check(line: str):

    if "#" in line:
        if "todo" in ("").join(line.split("#")[1:]).lower():
            return ("S005", "TODO found (in comments only and case-insensitive)")

def blank_line_check(line: str):

    global blanklines

    if line == "\n":
        blanklines += 1
    elif line != "\n" and blanklines <= 2:
        blanklines = 0
    elif blanklines > 2:
            blanklines = 0
            return ("S006", "More than two blank lines preceding a code line (applies to the first non-empty line)")

def construction_space_check(line: str):

    if line.lstrip().startswith("def"):
        constructor = "def"
    elif line.lstrip().startswith("class"):
        constructor = "class"
    else:
        return

    template = f"^{constructor}\\s[a-zA-Z_]"
    if re.match(template, line.lstrip()):
        return
    else:
        return ("S007", f"Too many spaces after '{constructor}'")

def camel_case_check(line: str):

    if line.lstrip().startswith("class"):
        template = "^class\\s{0,}[A-Z]{1}[a-z]*"
    else:
        return

    if re.match(template, line.lstrip()):
        return
    else:
        name = (re.match(r"^\s{0,}\w+", line.lstrip("class "))).group(0)
        return ("S008", f"Class name '{name}' should be written in CamelCase")

def snake_case_check(line: str):

    if line.lstrip().startswith("def"):
        template = "^def\\s{0,}[_]{0,2}[a-z]+"
    else:
        return

    if re.match(template, line.lstrip()):
        return
    else:
        return ("S009", f"Function name should be written in snake_case")

def arg_snake_case_check(function_defs: list):
    template = "^_{0,2}[a-z]{1,}_?"
    to_return = []
    for node in function_defs:
        for arg in node.args.args:
            if re.match(template, arg.arg):
                pass
            else:
                to_return.append(("S010", f"Argument name {arg.arg} should be written in snake_case", node.lineno))
                break

    # with open("ast_errors.json", 'w') as f:
    #     json.dump(args, f)

    return to_return

def var_snake_case_check(var_assign: list):
    template = "^_{0,2}[a-z]{1,}_?"
    to_return = []
    for node in var_assign:
        try:
            if re.match(template, node.targets[0].id):
                continue
        except AttributeError:
            if re.match(template, node.targets[0].attr):
                continue

        to_return.append(("S011", f" Variable \'{node.targets[0].id}\' should be written in snake_case", node.lineno))

    return to_return

def def_arg_check(function_defs: list):
    to_return = []
    for node in function_defs:
        for arg in node.args.defaults:
            if isinstance(arg, ast.List | ast.Set | ast.Dict):
                to_return.append(("S012", f"The default argument value is mutable", node.lineno))
                break
    return to_return


def line_gen(path: str):
    with open(path, 'r') as f:
        content = f.readlines()
        with open("notes2.txt", 'w') as f:
            f.write(path)
            f.writelines(content)
    yield from content

def ast_getter(path: str):
    with open(path, 'r') as f:
        content = f.read()
    parsed_content = ast.parse(content)

    function_defs = [node for node in list(ast.walk(parsed_content)) if isinstance(node, ast.FunctionDef)]
    var_assignments = [node for node in list(ast.walk(parsed_content)) if isinstance(node, ast.Assign)]

    return function_defs, var_assignments

def format_output(result: list):
    with open("result.json", 'w') as f:
        json.dump(result, f)
    for item in result:
        print(f"{item.path}: Line {item.line//100}: {item.error[0]} {item.error[1]}")

def run_checks(file_path: str, line: str, index: int):

    global problem_list
    fun_defs, var_asgmnt = ast_getter(file_path)
    ast_errors = []
    line_error = ()

    CHECKS = (
        len_check,
        indent_check,
        semicolon_check,
        inline_comment_check,
        todo_check, blank_line_check,
        construction_space_check,
        camel_case_check,
        snake_case_check,
    )

    for func in CHECKS:
        check_result = func(line)
        if check_result:
            line_error = ResultItem(path=file_path, line=index, error=check_result)
            problem_list.append(line_error)
            index += 1

    arg_snake_case_errors = arg_snake_case_check(fun_defs)
    var_snake_case_errors = var_snake_case_check(var_asgmnt)
    def_arg_error = def_arg_check(fun_defs)
    ast_errors = arg_snake_case_errors + def_arg_error + var_snake_case_errors
    if ast_errors:
        for error in ast_errors:
            line_error = ResultItem(path=file_path, line=error[2]*100, error=(error[0], error[1]))
            if line_error not in problem_list:
                problem_list.append(line_error)



def analyse_file(file_path: str):
    global blanklines
    index = 100
    content = line_gen(file_path)

    while True:
        try:
            line = next(content)
            run_checks(file_path=file_path, line=line, index=index)
            index += 100
            index = (index // 100) * 100
        except StopIteration:
            blanklines = 0
            break

if __name__ == "__main__":
    problem_list = []
    command_line_input = sys.argv[1]
    files_to_process = get_input_files(command_line_input)
    for file in files_to_process:
        blanklines = 0
        analyse_file(file)

    format_output(problem_list)
