import FreeCAD, FreeCADGui, TechDraw, Draft, Part, os

__dir__ = os.path.dirname(__file__)

class StraightCut():
    def __init__(self, obj):
        self.Type = "straightcut"
        obj.addProperty("App::PropertyLink", "Part", "StraightCut", "Object to be cut")
        obj.addProperty("App::PropertyLink", "Tool", "StraightCut", "Object which which the part intersects")
        obj.Proxy = self

    def execute(self, obj):
        doc = FreeCAD.ActiveDocument
        sel = FreeCADGui.Selection.getSelection()
        if obj.Part is None and obj.Tool is None:
            if len(sel) == 2:
                obj.Part = sel[0]
                obj.Tool = sel[1]
            else:
                FreeCAD.Console.PrintError("Must select two bodies")
                return
        com = obj.Part.Shape.common(obj.Tool.Shape)
        comp = FreeCAD.ActiveDocument.addObject("Part::Feature", "Common")
        comp.Shape = com
        cl = comp.Shape.BoundBox.ZLength
        view = Draft.makeShape2DView(comp)
        view.recompute()
        shp = view.Shape
        wire = TechDraw.findOuterWire(shp.Edges)
        doc.removeObject(view.Name)
        doc.removeObject(comp.Name)
        face = Part.Face(wire)
        extr = face.extrude(FreeCAD.Vector(0, 0, cl))
        cut = obj.Part.Shape.cut(extr)
        obj.Shape = cut
        obj.Part.Parents[0][0].addObject(obj)
        obj.Part.Visibility = False

class ViewProviderStraightCut:
    def __init__(self, obj):
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        self.Object = obj.Object
        return

    def claimChildren(self):
        objs = []
        objs.append(self.Object.Part)
        objs.append(self.Object.Tool)
        return objs

    def updateData(self, fp, prop):
        return

    def getDisplayModes(self,obj):
        return []

    def getDefaultDisplayMode(self):
        return "Shaded"

    def onChanged(self, vp, prop):
        return

    def getIcon(self):
        return os.path.join(__dir__, 'StraightCut.svg')

    def __getstate__(self):
        return None

    def __setstate__(self,state):
        return None

class AddStraightCut:
  def GetResources(self):
    return {'Pixmap' : os.path.join(__dir__, 'StraightCut.svg'),
            'MenuText': 'Straight Cut',
            'Accel': "C",
            'ToolTip' : """
                Make a straight cut through a body to fit an intersecting body
                1. Select the body that needs to be cut
                2. Select the intersecting body
                3. Click this tool
            """}

  def Activated(self):
    doc = FreeCAD.ActiveDocument
    obj = doc.addObject('Part::FeaturePython', "StraightCut")
    sel = FreeCADGui.Selection.getSelection()
    StraightCut(obj)
    ViewProviderStraightCut(obj.ViewObject)
    doc.recompute()
    return

  def IsActive(self):
    if len(FreeCADGui.Selection.getSelection()) < 2 :
      return False
    return True

FreeCADGui.addCommand("StraightCut", AddStraightCut())
