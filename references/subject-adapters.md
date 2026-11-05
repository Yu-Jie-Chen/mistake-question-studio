# Subject adapters

Load only the section for the current subject. These adapters refine the general workflow; they do not override source fidelity.

## Physics

### Must preserve

- Object/system boundary: which bodies are included in "系统".
- Frame and direction: upward/downward, left/right, positive direction.
- Given quantities and units: $m$, $v$, $\mu$, $R$, $E$, $B$, $g$.
- Diagram topology: strings, pulleys, contacts, circuits, rays, fields.
- State: rest, uniform motion, collision, equilibrium, steady state.

### Common extraction errors

- $v$ vs $V$, $m$ vs $M$, $p$ vs $P$;
- subscripted quantities $v_1, v_2$ flattened to $v1, v2$;
- $\mu$ read as $u$;
- "光滑" (frictionless) omitted;
- "轻绳/轻杆" omitted;
- "最大静摩擦力等于滑动摩擦力" omitted;
- a figure's direction arrow dropped;
- an angle given relative to the vertical read as relative to the horizontal.

### Figure rules

- Remove student-added $N$, $f$, $mg$, $F$, acceleration arrows, and auxiliary lines.
- Keep printed force arrows if the question itself provides them, but label them exactly.
- Preserve circuit symbols, polarity, meter positions, and switch state.
- Preserve ray directions, normals, and interface order.
- Preserve pulley/string topology: fixed end, free end, which segment is vertical/horizontal.
- Do not "fix" a diagram that is intentionally schematic.

### Analysis style

1. Choose the object/system.
2. Draw or describe the free-body/field/circuit model.
3. State the principle (Newton, energy, momentum, Kirchhoff, lens equation, etc.).
4. Substitute with units.
5. Check direction, sign, limiting case, and units.

### Answer formatting

- Give magnitude and direction for vectors.
- Keep $g$ as the value stated in the question; do not silently use 9.8 if 10 is given.
- Use the syllabus's significant-figure convention.
- For "求……大小", do not add a direction unless asked or needed.

## Chemistry

### Must preserve

- Reaction conditions: temperature, pressure, catalyst, light, solvent.
- State symbols: (s), (l), (g), (aq).
- Charges and oxidation states.
- Structural information: bond order, rings, functional groups, stereochemistry.
- Apparatus: joints, stoppers, delivery tubes, heating, gas collection, liquid levels.
- Data: molar mass, concentration, volume, yield.

### Common extraction errors

- $ \rightarrow $ vs $ \rightleftharpoons $;
- `+` in a reagent vs `+` between products;
- missing state symbols;
- $ \mathrm{Fe^{2+}} $ vs $ \mathrm{Fe^{3+}} $;
- formula subscripts flattened: $ \mathrm{H_2O} $ → `H2O` (acceptable in plain text, but restore subscripts in the card);
- gas collection method omitted;
- "过量/少量" omitted;
- stereochemistry ignored.

> The default formula renderer does **not** support mhchem `\ce{}`. Write `\mathrm{H_2O}`, `\mathrm{Fe^{2+}}`, `\rightarrow`, and `\rightleftharpoons` instead. If an equation is too complex for the renderer, set it as a clean formula image or use plain text with subscripts.

### Figure rules

- Preserve apparatus geometry; do not replace a specific setup with a generic flask.
- Keep gas flow arrows, heating source, and collection method.
- Keep liquid levels and labels.
- For organic structures, use a chemistry-aware editor or precise SVG; do not approximate bond angles.
- Keep charges and lone pairs if the question uses them.

### Analysis style

1. Identify the species and the reaction type.
2. Write the balanced equation with states.
3. Convert quantities to moles; show the limiting reagent.
4. Apply the relevant principle (stoichiometry, equilibrium, electrochemistry, kinetics).
5. State the final substance/amount with units.

### Answer formatting

- Balance equations; include conditions above/below the arrow.
- Use the correct state symbols.
- For "离子方程式", cancel spectator ions.
- For organic names, use the syllabus's nomenclature.

## Mathematics

### Must preserve

- Exact wording of definitions, domains, and constraints.
- Point labels, order, and incidence.
- Given lengths/angles and whether a figure is "not to scale".
- Function notation, domains, and intervals.
- Table/data precision.

### Common extraction errors

- $ \angle A $ vs $ \angle ABC $;
- $AB$ (segment length) vs $AB$ (line);
- $f(x)$ vs $f^{-1}(x)$;
- interval open/closed endpoints;
- "整数" / "正整数" / "非负整数" omitted;
- a diagram's right-angle or equal-length marks lost;
- a graph's asymptote or excluded point lost.

### Figure rules

- Preserve construction marks: right angles, equal segments, parallel marks, arcs, tangency.
- Keep point labels and their order.
- Do not redraw a "similar" figure with different proportions if lengths matter.
- For function graphs, preserve axes, intercepts, asymptotes, marked points, and domain endpoints.
- If the figure is "示意图" (not to scale), say so; do not imply scale accuracy.

### Analysis style

1. Restate the givens and the goal.
2. Choose a method (algebra, geometry, calculus, probability).
3. Show the key transformation, not every arithmetic line.
4. State the domain/constraint check.
5. Give the exact answer; decimal approximations only if requested.

### Answer formatting

- Use exact forms ($\sqrt{3}$, $\pi$, fractions) unless the question asks for decimals.
- Include units only for quantities that have them.
- For sets/intervals, use the syllabus notation.
- For "证明", end with the conclusion explicitly.

## English

### Must preserve

- Passage paragraphs and line numbers.
- Blanks and their numbers.
- Options A/B/C/D exactly.
- Instructions ("Read the passage...", "Choose the best answer...").
- Italics/bold used for emphasis.
- Punctuation that changes meaning.

### Common extraction errors

- line numbers dropped;
- a blank replaced by the answer;
- options merged into one line;
- "NOT" / "EXCEPT" missed;
- passage and questions separated across pages;
- grammar corrected silently;
- a table's row/column order lost.

### Figure rules

- Usually no figure; preserve tables, charts, and line-numbered layout.
- If a chart carries data, keep axes, units, and legend.
- Do not translate unless asked; if translating, keep the source alongside.

### Analysis style

1. Identify the question type (detail, inference, vocabulary, main idea, structure).
2. Quote or paraphrase the evidence location.
3. Explain why the correct option fits.
4. Explain why the distractors fail.
5. For grammar/fill, state the rule and the context.

### Answer formatting

- Give the option letter and, for teaching cards, the option text.
- For fill-in answers, preserve the required form (tense, number, case).
- For writing tasks, provide a model answer and a scoring checklist, not just a sample.

## Biology

### Must preserve

- Structure names and leader lines.
- Orientation (left/right, upper/lower).
- Process direction (blood flow, nerve impulse, water flow).
- Genetic notation: alleles, crosses, genotypes, phenotypes.
- Experimental groups and controls.

### Common extraction errors

- a label's leader line pointing to the wrong structure;
- $A$ vs $a$ case lost;
- "显性/隐性" omitted;
- a process arrow reversed;
- a control group omitted;
- a diagram simplified until a structure disappears.

### Figure rules

- Keep leader lines attached to the correct structure.
- Do not simplify away a structure the question asks to identify.
- Preserve orientation and relative position.
- For遗传 diagrams, preserve the cross format and generation labels (P, F1, F2).

### Analysis style

1. Identify the biological level (molecule, cell, tissue, organ, ecosystem).
2. State the process and the direction.
3. Apply the relevant principle (genetics, homeostasis, evolution, ecology).
4. Use the data/experiment to justify.
5. State the conclusion in biological terms.

## Geography

### Must preserve

- North arrow, scale, legend, contour interval.
- Coordinates, direction, and relative location.
- Map labels and boundaries.
- Data units and time scales.

### Common extraction errors

- north arrow lost;
- scale/contour interval omitted;
- a map cropped so the location is ambiguous;
- legend symbols lost;
- "冬/夏" or "1月/7月" omitted.

### Figure rules

- Do not redraw a map from memory; crop it or use a licensed base.
- Keep the north arrow, scale, legend, and contour values.
- Preserve the map's orientation and extent.

### Analysis style

1. Locate the region and scale.
2. Read the map/graph data.
3. Explain the physical/human process.
4. Link cause and effect.
5. State the answer with direction/location.

## History and politics

### Must preserve

- Source excerpt, author, date, and context.
- Timeline order.
- Terms and names.
- The question's "根据材料" vs "结合所学" distinction.

### Common extraction errors

- source attribution dropped;
- date/period shifted;
- a quotation merged with the question's wording;
- "根本原因/直接原因" confused;
- multiple materials merged into one.

### Analysis style

1. Identify the source and period.
2. Extract the material's claim.
3. Connect to the relevant historical/political knowledge.
4. Compare/contrast or evaluate.
5. Conclude with a direct answer.

## Cross-subject rules

- Keep units and significant figures consistent with the source.
- Keep tables as tables.
- Keep figure/table callouts attached to the right asset.
- Do not translate technical terms inconsistently.
- If the subject is unclear, infer from the notation and ask only if the answer depends on it.
- For mixed subjects (e.g., physical chemistry, biostatistics), load both adapters and let the stricter notation rule win.
