import json
import sys

TERMINATORS = set(["jmp", "br", "ret"])

def create_blocks(prog):
    blocks = []
    block = []
    for func in prog["functions"]:
        for instruction in func["instrs"]:
            if "op" in instruction: # actual instruction
                block.append(instruction)
                if instruction["op"] in TERMINATORS:
                    blocks.append(block)
                    block = []
            else: # presumably a label
                blocks.append(block)
                block = [instruction]
        blocks.append(block)
    return blocks

class BlockNode:
    def __init__(self, val, next=None, br_true=None, br_false=None):
        self.val = val
        self.next = next
        self.br_true = br_true
        self.br_false = br_false

def mycfg(prog):
    blocks = create_blocks(prog)
    print(f"Blocks: {blocks}")

    label_dict = dict()
    blocks = [BlockNode(val=block) for block in blocks]
    for block in blocks:
        if "label" in block.val[0]:
            label_dict[block.val[0]["label"]] = block
    
    for i, block in enumerate(blocks):
        terminator = block.val[-1]
        match terminator["op"]:
            case "jmp":
                block.next = label_dict[terminator["labels"][0]]
            case "br":
                block.br_true = label_dict[terminator["labels"][0]]
                block.br_false = label_dict[terminator["labels"][1]]
            case "ret":
                pass
            case _: # no terminator, just go to the next block sequentially
                block.next = blocks[i + 1] if i + 1 < len(blocks) else None

    print(f"root: {blocks[0].next.val}")




def main():
    json_text = sys.stdin.read()
    parsed_json = json.loads(json_text)
    print(f"Parsed JSON: {parsed_json}")

    mycfg(parsed_json)

if __name__ == "__main__":
    main()
    