import re

redos = r"^(a+)+$"

data = "a" * 100 + "b"

# ruleid: regex_dos
pattern = re.compile(redos)
pattern.search(data)