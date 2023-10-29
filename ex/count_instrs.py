import json
import sys

def count_instrs():
    json_text = sys.stdin.read()
    prog = json.loads(json_text)
    instr_count = {}
    for func in prog["functions"]:
        for instruction in func["instrs"]:
            if "op" in instruction:
                op = instruction["op"]
                if op in instr_count:
                    instr_count[op] += 1
                else:
                    instr_count[op] = 1
    print(f"Instruction counts:\n{instr_count}")


if __name__ == "__main__":
    count_instrs()