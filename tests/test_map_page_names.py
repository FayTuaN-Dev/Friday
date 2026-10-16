import re
from collections import Counter

from friday.ui.desktop.scenes.map_page import page


def test_the_map_scripts_never_declare_the_same_name_twice():
    # Constaté : un deuxième « const fade » (météo, après le globe) aurait cassé toute la carte
    names = []
    for line in page().splitlines():
        if match := re.match(r"(?:const|let|function)\s+([\w$]+)", line):
            names.append(match.group(1))
        if match := re.match(r"let\s+(.+?);", line):
            names += [n.split("=")[0].strip() for n in match.group(1).split(",")[1:]]
    twice = [name for name, n in Counter(names).items() if n > 1]
    assert names and not twice, twice
