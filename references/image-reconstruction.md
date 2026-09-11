# Reconstructing an image

1. Open the actual supplied image before identifying circuitry. If decoding fails, check whether the file is really an image (a `.png` filename can contain text); do not mistake a partial or tolerant decode for the full circuit. Report damaged input and request an intact copy when connectivity is unavailable. Inspect valid images at readable resolution. Crop/zoom small regions with available viewing tools. A PCB photograph or breadboard photo can hide traces; do not infer a complete schematic from visible placement alone.
2. List visible component references, types, values, terminal labels, arrows, and polarities. Keep an unknown value as `?` or a named placeholder; do not guess it from a common textbook circuit.
3. Trace continuous wires. Give each net a temporary name and record every connected terminal. Use separate names for the two sides of a component. Dots, T-junctions, crossing bridges, and open circles carry different meanings.
4. Resolve meaningful ambiguity before calling the result faithful. Example: “The center crossing is too blurred to tell whether it is connected. Please provide a crop.” If a useful draft is requested, label the chosen interpretation and unresolved region explicitly.
5. Recreate topology before matching coordinates. Preserve reference designators even if numeric values are unknown. Rotate/mirror symbols only after confirming terminal anchors and polarity.
6. Compare the rendered diagram region by region and branch by branch with the source. Count components, trace each net, and compare labels, signs and arrows. Record what could not be verified.

A screenshot of an existing schematic is often enough for reconstruction. A photograph of a populated board generally cannot establish hidden vias, inner layers, or exact IC pin functions; a schematic, continuity data, or part documentation may be necessary. Do not claim an automatically extracted netlist or electrical-rule check when none ran.
