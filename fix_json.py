import re

with open('data/ground_truth.json', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_string = False
for line in lines:
    # count unescaped quotes
    quotes = len(re.findall(r'(?<!\\)"', line))
    if quotes % 2 != 0:
        in_string = not in_string
    
    if in_string:
        # if we are in a string and the line ends with a newline, replace it with \n
        if line.endswith('\n'):
            line = line[:-1] + '\\n'
    new_lines.append(line)

with open('data/ground_truth.json', 'w', encoding='utf-8') as f:
    f.write("".join(new_lines))

print("Fixed newlines in JSON.")
