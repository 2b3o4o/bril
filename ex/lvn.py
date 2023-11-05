import sys
import json
from typing import Tuple, Dict, Optional
import ipdb

TERMINATORS = set(["jmp", "br", "ret"])
VAR_USER_OPCODES = set(["add", "mul", "sub", "div", "eq", "lt", "gt", "le", "ge", "not", "and", "or", "call", "br", "ret", "id", "print"]) # CORE ONLY << vvv
VAR_SETTER_OPCODES = set(["add", "mul", "sub", "div", "eq", "lt", "gt", "le", "ge", "not", "and", "or", "call", "id", "const"])
COMMUTATIVE_OPCODES = set(["add", "mul", "eq", "and", "or"])

BrilExpr = Tuple[str, str, str] | str # Either (op, arg1, arg2) or a single literal resulting from static evaluation
def isinstance_BrilExpr(obj) -> bool: # isinstance fails on type unions, so we have to check the type like this.
    if isinstance(obj, (str, tuple)):
        if isinstance(obj, tuple):
            return len(obj) == 3 and all(isinstance(e, str) for e in obj)
        return True
    else:
        return False

def is_bril_literal(string) -> bool:
    if string in ["True", "False"]: # boolean literal
        return True
    try:
        int(string)
    except ValueError:
        return False
    return True # integer literal

def lvn_expr(instr) -> BrilExpr:
    """Take an instruction and generate an expression for the value it computes.
    Format: (opcode, arg1, arg2)
    At this point we don't evaluate whether the expression is constant or has constant parts. Just change the format."""
    # val_expr: (str, str, str) = ("add", "#1", "2")
    if instr["op"] == "const":
        return str(instr["value"])
    args = instr["args"]
    return (instr["op"], args[0], args[1] if len(args) > 1 else "")

def eval_static_expr(expr: BrilExpr) -> BrilExpr:
    """Take an expression and try to reduce it to a literal."""
    assert isinstance_BrilExpr(expr)
    if isinstance(expr, str):
        return expr # already a literal
    opcode, arg1, arg2 = expr
    if not (is_bril_literal(arg1) and is_bril_literal(arg2)):
        return expr # we need to know what the operands are at compile time to perform static evaluation, in this case we don't.
    # TODO: python arithmetic operators are not exactly equivalent to those in bril, I'd imagine. so all/most of these are probably incorrect in some edge cases
    # I also have no error handling whatsoever here. Should I add some, or should I assume checking for syntax errors is already handled by this point?
    match opcode:
        case "add":
            result = int(arg1) + int(arg2)
        case "mul":
            result = int(arg1) * int(arg2)
        case "sub":
            result = int(arg1) - int(arg2)
        case "div":
            result = int(arg1) // int(arg2)
        case "eq":
            result = int(arg1) == int(arg2)
        case "lt":
            result = int(arg1) < int(arg2)
        case "gt":
            result = int(arg1) > int(arg2)
        case "le":
            result = int(arg1) <= int(arg2)
        case "ge":
            result = int(arg1) >= int(arg2)
        case "not":
            result = arg1 != "True"
        case "and":
            result = arg1 == arg2 == "True"
        case "or":
            result = "True" in (arg1, arg2)
        case _:
            print(f"eval_static_expr encountered unknown opcode, and was not able to evaluate the expression. opcode={opcode}", sys.stderr)
    return str(result)

class LvnEntry:
    def __init__(self, target: str, expr: BrilExpr):
        assert isinstance(target, str)
        assert isinstance_BrilExpr(expr)
        self.canonical_var: str = target
        self.expr: BrilExpr = expr
        self.is_static_val: bool = isinstance(expr, str)

def rewrite_instr(expr: BrilExpr=None, entry: LvnEntry=None, result_type: str=None): # TODO: handle types better? I completely forgot about them until now lmao
    instr = {}
        # "dest": entry.canonical_var,
    if entry:
        instr["dest"] = entry.canonical_var
        if isinstance(entry.expr, str): # static expression, let's just define a const
            instr["op"] = "const"
            instr["value"] = entry.expr
        if result_type:
            assert isinstance(result_type, str)
            instr["type"] = result_type
        else: # we're DYNAMIC and FAST-MOVING.
            op, arg1, arg2 = entry.expr
            instr["op"] = op
            args = [arg1]
            if arg2:
                args.append(arg2)
            instr["args"] = args
    elif expr:
        assert isinstance_BrilExpr(expr)
        op, arg1, arg2 = expr
        instr["op"] = op
        args = []
        if arg1:
            args.append(arg1)
        if arg2:
            args.append(arg2)
        if args:
            instr["args"] = args
    return instr

class LvnTable:
    def __init__(self):
        self.entries: [LvnEntry] = []
        self.expr_to_entry: Dict[LvnEntry, int] = {}
        self.var_to_entry: Dict[str, int] = {}

    def substitute_arg(self, arg: str) -> str:
        if is_bril_literal(arg):
            return arg
        entry: LvnEntry = self.get_entry_for_variable(arg)
        if entry: # This variable maps to a value in the table
            if entry.is_static_val: # this variable maps to a static value in the table. great! we'll just replace it with that const.
                static_val = entry.expr
                assert isinstance(static_val, str)
                return static_val
            else: # we need to keep this value dynamic. but, we should make sure we're using its canonical name.
                return entry.canonical_name
        return ""

    def reduce_expr(self, expr: BrilExpr) -> BrilExpr:
        """Take an expression and simplify it:
        1. If an arg can be replaced with a constant value, do that.
        2. If the opcode is for a commutative function then sort the args for later comparison."""
        assert isinstance_BrilExpr(expr)
        if isinstance(expr, str):
            return expr # If the expression is already just a constant, there's nothing to be reduced.
        opcode, arg1, arg2 = expr
        args = [self.substitute_arg(arg1), self.substitute_arg(arg2)]
        if opcode in COMMUTATIVE_OPCODES:
            args.sort()
        return (opcode, args[0], args[1])
    
    def get_entry_for_expr(self, expr: (str, str, str)) -> (Optional[LvnEntry], Optional[int]):
        index: Optional[int] = self.expr_to_entry.get(expr)
        return self.entries[index] if index else None, index

    def new_entry(self, target: str, expr: BrilExpr) -> LvnEntry:
        entry = LvnEntry(target, expr)
        self.entries.append(entry)
        index = len(self.entries) - 1
        self.expr_to_entry[expr] = index
        self.map_var_to_entry(target, index)
        assert self.entries[index]
        return self.entries[index]

    def map_var_to_entry(self, var: str, entry_index: int):
        assert var
        self.var_to_entry[var] = entry_index
    
    def get_entry_for_variable(self, var: str):
        assert isinstance(var, str)
        index = self.var_to_entry.get(var)
        if index == None:
            return None
        return self.entries[index]


def lvn(prog):
    table = LvnTable()
    for func in prog["functions"]:
        new_instrs = []
        for instr in func["instrs"]:
            if "label" in instr or instr["op"] in TERMINATORS: # entering new block, start new lvn scope
                rewritten_instr = instr
                table = LvnTable()
            elif instr["op"] in (VAR_USER_OPCODES | VAR_SETTER_OPCODES):
                expr: BrilExpr = lvn_expr(instr) # op #1 #2
                expr = table.reduce_expr(expr)
                expr = eval_static_expr(expr)
                entry: Optional[LvnEntry]
                entry_index: Optional[int]
                entry, entry_index = table.get_entry_for_expr(expr)
                if entry and entry_index: # value already exists
                    table.map_var_to_entry(instr["dest"], entry_index)
                    rewritten_instr = rewrite_instr(entry=entry, result_type=instr["type"])
                elif "dest" in instr: # new value
                    entry = table.new_entry(instr["dest"], expr)
                    rewritten_instr = rewrite_instr(entry=entry, result_type=instr["type"])
                else:
                    rewritten_instr = rewrite_instr(expr=expr)
                # rewritten_instr = rewrite_instr(entry=entry, result_type=instr["type"]) if "type" in instr else rewrite_instr(entry=entry)
            else:
                rewritten_instr = instr
            new_instrs.append(rewritten_instr)
        func["instrs"] = new_instrs
    return prog


def main():
    json_text = sys.stdin.read()
    prog = json.loads(json_text)

    # sys.stdin = open('/dev/tty', 'r')
    # ipdb.set_trace()

    reconstructed_program = lvn(prog)

    print(json.dumps(reconstructed_program, indent=4))

if __name__ == "__main__":
    main()