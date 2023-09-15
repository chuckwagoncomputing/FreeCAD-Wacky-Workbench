import FreeCAD, FreeCADGui, TechDraw, Draft, Part, os

__dir__ = os.path.dirname(__file__)

def placementSub(a, b):
    v1 = a.Base
    v2 = b.inverse().Base
    r1 = a.Rotation
    r2 = b.Rotation
    return FreeCAD.Placement(v1 + v2, r1.multiply(r2.inverted()))

def placementAdd(a, b):
    v1 = a.Base
    v2 = b.inverse().Base
    r1 = a.Rotation
    r2 = b.Rotation
    return FreeCAD.Placement(v1 - v2, r1.multiply(r2))

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
        # s[part|tool] = selected
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
                    obj.Part = spart.LinkedObject
                    obj.AttachedTool = stool.Name
                    obj.Tool = stool.LinkedObject
                    linked = True
                else:
                    obj.Part = spart
                    obj.Tool = stool
            else:
                FreeCAD.Console.PrintError("Must select two bodies or links to bodies")
                return
        # Recomputation
        else:
            return
            # Updating to tip of the body if we're not pointed at it anymore.
            tpart = obj.Part.Parents[0][0].Tip
            if tpart != obj.Part:
                if tpart != obj:
                    obj.Part = tpart
                else:
                    obj.Part = obj.BaseFeature
            # If we have a link that points to the part (assume the same for tool)
            if obj.AttachedPart != "":
                spart = doc.getObject(obj.AttachedPart)
                stool = doc.getObject(obj.AttachedTool)
                stool.recompute()
                linked = True

        part = obj.Part
        # If the part and tool are a body (probably the case on inital creation)
        if obj.Part.TypeId == 'PartDesign::Body':
            obj.Part = obj.Part.Tip
        if obj.Tool.TypeId == 'PartDesign::Body':
            shb = part.newObject('PartDesign::ShapeBinder','ShapeBinder')
            shb.Support = [obj.Tool,'']
            obj.Tool = shb
            shb.recompute()
            shb.Visibility = False
        tool = obj.Tool

        if not obj.Part.isDerivedFrom('PartDesign::Feature'): # or not tool.isDerivedFrom('PartDesign::Feature'):
            FreeCAD.Console.PrintError("can't use selection")
            return


        # common shape, which will be generated differently in different scenarios
        com = None
        pl = part.Placement
        part.Placement = FreeCAD.Placement(FreeCAD.Vector(0,0,0),FreeCAD.Rotation(FreeCAD.Vector(0,0,1),0))
        tool.Placement = placementSub(tool.Placement, pl)

        # the easy mode
        if not linked:
            com = part.Shape.common(tool.Shape)
        # the hard mode
        else:
            attached = None
            invert = False
            # we have to figure out which was attached to which
            # sometimes the part can be attached to the tool
            if spart.AttachedTo.split('#')[0] == stool.Name:
                attached = spart
                invert = True
            elif stool.AttachedTo.split('#')[0] == spart.Name:
                attached = stool
            else:
                FreeCAD.Console.PrintError("not attached")
                return
            placement = attached.LinkPlacement
            pat = doc.getObject(attached.AttachedTo.split('#')[0])
            while pat != None:
                placement = placementSub(placement, pat.Placement)
                pat = doc.getObject(pat.AttachedTo.split('#')[0])
            temp = FreeCAD.ActiveDocument.addObject("Part::Feature", "TempBody")
            temp.Shape = tool.Shape
            if invert:
                temp.Placement = placement.inverse()
            else:
                temp.Placement = placement
            com = part.Shape.common(temp.Shape)
            doc.removeObject(temp.Name)
        comp = FreeCAD.ActiveDocument.addObject("Part::Feature", "Common")
        comp.Shape = com
        cl = comp.Shape.BoundBox.ZLength
        vec = part.Placement.Rotation.multVec(FreeCAD.Vector(0,0,1))
        view = Draft.makeShape2DView(comp, vec)
        view.recompute()
        shp = view.Shape
        wire = TechDraw.findOuterWire(shp.Edges)
        doc.removeObject(view.Name)
        doc.removeObject(comp.Name)
        face = Part.Face(wire)
        extr = face.extrude(part.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, cl)))
        cut = part.Shape.cut(extr)
        part.Placement = pl
        tool.Placement = placementAdd(tool.Placement, pl)
        obj.Shape = cut
        if obj.Parents[0][0] == None:
            part.addObject(obj)

class ViewProviderStraightCut:
    def __init__(self, obj):
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        self.Object = obj.Object
        return

    def claimChildren(self):
        objs = []
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
