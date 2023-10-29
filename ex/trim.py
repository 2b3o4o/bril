import json
import sys

TERMINATORS = set(["jmp", "br", "ret"])
VAR_USER_OPCODES = set(["add", "mul", "sub", "div", "eq", "lt", "gt", "le", "ge", "not", "and", "or", "call", "br", "ret", "id", "print"]) # CORE ONLY
VAR_SETTER_OPCODES = set(["add", "mul", "sub", "div", "eq", "lt", "gt", "le", "ge", "not", "and", "or", "call", "id", "const"])

def trim_unused_var_assignments(prog) -> bool:
    modified_program = False
    for func in prog["functions"]:
        used_variables = set()
        for instr in func["instrs"]:
            if "op" in instr and instr["op"] in VAR_USER_OPCODES:
                used_variables.update(instr["args"])
        new_instrs = []
        for instr in func["instrs"]:
            if "op" in instr and instr["op"] in VAR_SETTER_OPCODES and instr["dest"] not in used_variables:
                # print(f"Deleting {instr}")
                modified_program = True
            else:
                new_instrs.append(instr)
        if modified_program:
            func["instrs"] = new_instrs
    return modified_program

def trim_overwritten_vars(prog) -> bool:
    """Remove variable assignment to variables which are reassigned to before they are used.
    Operates on the scope of individual blocks."""
    # for block in func_cfg
    modified_program = False
    assigned_vars = set()
    """ ^^^ if a variable is in this set, it means any assignments to it we encounter (while iterating backwards)
    are subsequently overwritten and thus irrelevant """
    for func in prog["functions"]:
        reduced_instrs = []
        modified_func = False
        for instr in func["instrs"][::-1]: # iterate backwards through func
            trim_this_instr = False
            if "label" in instr or instr["op"] in TERMINATORS: # entering new block, start clean
                assigned_vars = set()
            elif instr["op"] in VAR_SETTER_OPCODES:
                if instr["dest"] in assigned_vars: # redundant instruction
                    trim_this_instr = True
                    modified_func = True
                else:
                    assigned_vars.add(instr["dest"])
            elif instr["op"] in VAR_USER_OPCODES: 
                for arg in instr["args"]: # we're using any args we identify here, prior definitions of those vars are important!
                    assigned_vars.discard(arg)

            if not trim_this_instr:
                reduced_instrs.insert(0, instr)
        if modified_func:
            func["instrs"] = reduced_instrs
            modified_program = True
    return modified_program


def main():
    json_text = sys.stdin.read()
    prog = json.loads(json_text)

    modified_program = True
    while modified_program:
        modified_program = trim_unused_var_assignments(prog) or trim_overwritten_vars(prog)

    print(json.dumps(prog, indent=4))

if __name__ == "__main__":
    main()
    