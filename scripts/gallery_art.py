"""Compose a README preview from actual vector circuit exports, without redrawing."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def overview(folder):
    folder = Path(folder)
    cards = [
        ("divider-loaded", "01  /  Loaded divider", "5 V input  /  1.666667 V output"),
        ("bridge-unbalanced", "02  /  Unbalanced bridge", "Loaded midpoint equations  /  +0.413223 V"),
        ("series-rlc", "03  /  Series RLC", "Differential output across R  /  DC + AC checks"),
        ("opamp-summer", "04  /  Weighted summer", "Explicit feedback pins  /  finite-gain ideal model"),
    ]
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1280" height="934" viewBox="0 0 1280 934" role="img" aria-labelledby="title desc">',
             '<title id="title">Circuit Diagram Generator: four actual verified schematics</title>',
             '<desc id="desc">Loaded divider, Wheatstone bridge, series RLC, and weighted summer. Full editable diagrams and verification results are linked in the repository.</desc>',
             '<rect width="1280" height="934" rx="20" fill="#EEF3F6"/>',
             '<path d="M20 0H1260Q1280 0 1280 20V134H0V20Q0 0 20 0" fill="#142A40"/>',
             '<text x="32" y="57" fill="#FFFFFF" font-family="Arial,sans-serif" font-weight="700" font-size="36">From connections to clear schematics.</text>',
             '<text x="34" y="99" fill="#C6D5E3" font-family="Arial,sans-serif" font-size="19">12 valued circuits  ·  24 SPICE analyses  ·  Editable TeX, PDF, SVG and PNG</text>']
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    for index, (ident, heading, caption) in enumerate(cards):
        x, y = 24 + (index % 2) * 628, 158 + (index // 2) * 372
        lines.extend([f'<rect x="{x}" y="{y}" width="604" height="348" rx="12" fill="white" stroke="#DCE5EC"/>',
                      f'<text x="{x+22}" y="{y+34}" fill="#20334A" font-family="Arial,sans-serif" font-size="20" font-weight="700">{heading}</text>',
                      f'<text x="{x+22}" y="{y+325}" fill="#416777" font-family="Arial,sans-serif" font-size="16">{caption}</text>'])
        svg = ET.parse(folder / ident / (ident + ".svg")).getroot()
        viewbox = [float(n) for n in svg.attrib["viewBox"].split()]
        width, height = viewbox[2:]
        ratio = min(552 / width, 246 / height)
        svg.set("x", str(x + (604 - width * ratio) / 2))
        svg.set("y", str(y + 54 + (246 - height * ratio) / 2))
        svg.set("width", str(width * ratio))
        svg.set("height", str(height * ratio))
        mapping = {element.attrib["id"]: f"card{index}-" + element.attrib["id"]
                   for element in svg.iter() if "id" in element.attrib}
        for element in svg.iter():
            if "id" in element.attrib:
                element.set("id", mapping[element.attrib["id"]])
            for key, value in list(element.attrib.items()):
                if key != "id":
                    element.set(key, re.sub(r"#([\w.-]+)", lambda m: "#" + mapping.get(m[1], m[1]), value))
        lines.append(ET.tostring(svg, encoding="unicode"))
    lines.extend(['<text x="34" y="911" fill="#516B7F" font-family="Arial,sans-serif" font-size="16">Actual generated vector artwork. Ideal-model checks are documented; physical hardware performance is outside scope.</text>', '</svg>'])
    (folder / "overview.svg").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    overview(parser.parse_args().folder)
