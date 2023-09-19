# FreeCAD-Wacky-Workbench
A Wacky workbench of Wacky tools for FreeCAD

## StraightCut
Make a hole straight through a part (base) that will fit an intersecting part (tool). Great for 2D CNC such as a plasma table or router table.
You can use this on:
- PartDesign Bodies
- PartDesign Features
- PartDesign Body links in Assembly4
- Parts

The cutting axis is asuumed to be the Z axis of the base.
If the selected base is a PartDesign Body, Feature, or a link to a Body, and the result has more than one separate solid, only the largest will be kept. If the selected base is a Part, all solids will be kept. You can replicate the same behavior by using a CompoundFilter on the result.

## ExportDXF
Automatically re-export a face as DXF whenever the model changes
