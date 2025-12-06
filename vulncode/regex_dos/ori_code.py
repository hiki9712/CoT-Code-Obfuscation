import re

redos = r"^(a+)+$"

data = "foo"

# ruleid: regex_dos
pattern = re.compile(redos)
pattern.search(data)