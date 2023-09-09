import FreeCAD, FreeCADGui, TechDraw, Draft, Part, os

__dir__ = os.path.dirname(__file__)

class StraightCut():
    def __init__(self, obj):
        self.Type = "straightcut"
        obj.addProperty("App::PropertyLink", "Part", "StraightCut", "Object to be cut")
        obj.addProperty("App::PropertyLink", "Tool", "StraightCut", "Object which which the part intersects")
        # Very hacky storing as strings to avoid loops.
        obj.addProperty("App::PropertyString", "AttachedPart", "StraightCut", "Object which links to Part")
        obj.addProperty("App::PropertyString", "AttachedTool", "StraightCut", "Object which links to Tool")
        obj.Proxy = self

    def execute(self, obj):
        doc = FreeCAD.ActiveDocument
        sel = FreeCADGui.Selection.getSelection()
        # s[part|tool] = selected; l[part|tool] = linked to
        part = None
        spart = None
        tool = None
        stool = None
        linked = False
        # Initial generation
        if obj.Part is None and obj.Tool is None:
            if len(sel) == 2:
                spart = sel[0]
                stool = sel[1]
                if spart.TypeId == 'App::Link' and stool.TypeId == 'App::Link':
                    obj.AttachedPart = spart.Name
                    part = spart.LinkedObject
                    obj.AttachedTool = stool.Name
                    tool = stool.LinkedObject
                    linked = True
                else:
                    part = spart
                    tool = stool
            else:
                FreeCAD.Console.PrintError("Must select two bodies or links to bodies")
                return
        # Recomputation
        else:
            # Updating to tip of the body if we're not pointed at it anymore.
            tpart = obj.Part.getParent().Tip
            if tpart != obj.Part:
                if tpart != obj:
                    obj.Part = tpart
                else:
                    obj.Part = obj.BaseFeature
            obj.Tool = obj.Tool.getParent().Tip
            # If we have a link that points to the part (assume the same for tool)
            if obj.AttachedPart != "":
                spart = doc.getObject(obj.AttachedPart)
                stool = doc.getObject(obj.AttachedTool)
                linked = True

        # If the part and tool are a body (probably the case on inital creation)
        if part.TypeId == 'PartDesign::Body' and tool.TypeId == 'PartDesign::Body':
            # Make doubly sure the tip isn't us
            if part.Tip == obj:
                part = obj.BaseFeature
            else:
                part = part.Tip
            tool = tool.Tip

        if not part.isDerivedFrom('PartDesign::Feature') or not tool.isDerivedFrom('PartDesign::Feature'):
            FreeCAD.Console.PrintError("can't use selection")
            return


        # common shape, which will be generated differently in different scenarios
        com = None
        # the easy mode
        if not linked:
            com = part.Shape.common(tool.Shape)
        # the hard mode
        else:
            fixed = None
            attached = None
            lattached = None
            # we have to figure out which was attached to which
            # sometimes the part can be attached to the tool
            if spart.AttachedTo.split('#')[0] == stool.Name:
                fixed = tool
                lattached = spart
                attached = part
            elif stool.AttachedTo.split('#')[0] == spart.Name:
                fixed = part
                lattached = stool
                attached = tool
            else:
                FreeCAD.Console.PrintError("not attached")
                return
            placement = lattached.LinkPlacement
            pat = doc.getObject(lattached.AttachedTo.split('#')[0])
            while pat != None:
                v1 = pat.Placement.Base
                v2 = placement.Base
                r1 = pat.Placement.Rotation
                r2 = placement.Rotation
                placement.Base = v2 - v1
                placement.Rotation = r2.multiply(r1.inverted())
                pat = doc.getObject(pat.AttachedTo.split('#')[0])
            temp = FreeCAD.ActiveDocument.addObject("Part::Feature", "TempBody")
            temp.Shape = attached.Shape
            temp.Placement = placement
            com = fixed.Shape.common(temp.Shape)
            doc.removeObject(temp.Name)
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
        cut = part.Shape.cut(extr)
        obj.Shape = cut
        obj.Part = part
        obj.Tool = tool
        if obj.getParent() == None:
            part.getParent().addObject(obj)

class ViewProviderStraightCut:
    def __init__(self, obj):
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        self.Object = obj.Object
        return

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
    obj = doc.addObject('PartDesign::FeaturePython', "StraightCut")
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
