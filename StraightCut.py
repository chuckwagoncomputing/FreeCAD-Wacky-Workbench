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
        obj.addProperty("App::PropertyLink", "Base", "StraightCut", "Object to be cut")
        obj.addProperty("App::PropertyLink", "Tool", "StraightCut", "Object which which the base intersects")
        # Very hacky storing as strings to avoid loops.
        obj.addProperty("App::PropertyString", "AttachedBase", "StraightCut", "Object which links to Base")
        obj.addProperty("App::PropertyString", "AttachedTool", "StraightCut", "Object which links to Tool")
        obj.Proxy = self

    def execute(self, obj):
        doc = FreeCAD.ActiveDocument
        sel = FreeCADGui.Selection.getSelection()
        # s[base|tool] = selected
        sbase = None
        stool = None
        base = None
        tool = None
        linked = False
        recompute = False
        keepLargest = False
        debug = False
        # Initial generation
        if obj.Base is None and obj.Tool is None:
            if len(sel) == 2:
                sbase = sel[0]
                stool = sel[1]
                lbase = None
                ltool = None

                if hasattr(doc, 'Assembly') and sbase.getParent():
                    lbase = list(filter(lambda o: o.TypeId == 'App::Link' and \
                        FreeCADGui.Selection.isSelected(doc.Assembly, o.Name + "." + sbase.Name + "."), sbase.getParent().InList))
                if sbase.TypeId == 'App::Link':
                    obj.AttachedBase = sbase.Name
                    obj.Base = sbase.LinkedObject
                    linked = True
                elif lbase:
                    obj.AttachedBase = lbase[0].Name
                    obj.Base = sbase
                    sbase = lbase[0]
                    linked = True
                else:
                    obj.Base = sbase

                if hasattr(doc, 'Assembly') and stool.getParent():
                    ltool = list(filter(lambda o: o.TypeId == 'App::Link' and \
                        FreeCADGui.Selection.isSelected(doc.Assembly, o.Name + "." + stool.Name + "."), stool.getParent().InList))
                if stool.TypeId == 'App::Link':
                    obj.AttachedTool = stool.Name
                    obj.Tool = stool.LinkedObject
                    linked = True
                elif ltool:
                    obj.AttachedTool = ltool[0].Name
                    obj.Tool = stool
                    stool = ltool[0]
                    linked = True
                else:
                    obj.Tool = stool

            else:
                FreeCAD.Console.PrintError("Must select two bodies or links to bodies")
                return

        # Recomputation
        else:
            recompute = True
            # If we have a link that points to the base (assume the same for tool)
            if obj.AttachedBase != "":
                sbase = doc.getObject(obj.AttachedBase)
                stool = doc.getObject(obj.AttachedTool)
                stool.recompute()
                linked = True

        if obj.Base.isDerivedFrom('PartDesign::Feature'):
            base = obj.Base.getParent()
            if base.Tip == obj:
                obj.Base = obj.BaseFeature
        elif obj.Base.isDerivedFrom('Part::Feature'):
            base = obj.Base

        if not recompute:
            if obj.Base.TypeId == 'PartDesign::Body':
                obj.Base = obj.Base.Tip

            if obj.Tool.TypeId == 'PartDesign::Body' or obj.Tool.isDerivedFrom('PartDesign::Feature'):
                if base.TypeId == 'PartDesign::Body':
                    shb = base.newObject('PartDesign::ShapeBinder','ShapeBinder')
                else:
                    shb = doc.addObject('PartDesign::ShapeBinder','ShapeBinder')
                shb.Support = [obj.Tool,'']
                shb.TraceSupport = True
                obj.Tool = shb
                shb.recompute()
                shb.Visibility = False

        tool = obj.Tool

        if obj.TypeId == 'PartDesign::FeaturePython':
            keepLargest = True

        # common shape, which will be generated differently in different scenarios
        com = None
        pl = base.Placement.copy()
        ptb = doc.addObject("Part::Feature", "TempBase")
        ptb.Shape = obj.Base.Shape
        ptb.Placement = FreeCAD.Placement(FreeCAD.Vector(0,0,0),FreeCAD.Rotation(FreeCAD.Vector(0,0,1),0))
        ttb = doc.addObject("Part::Feature", "TempTool")
        ttb.Shape = tool.Shape
        if tool.TypeId == 'PartDesign::ShapeBinder':
            ttb.Placement = tool.Placement
        else:
            tp = tool.Placement.copy()
            ttb.Placement = placementSub(tp, pl)
        base = ptb
        tool = ttb
        base.recompute()
        tool.recompute()

        # the easy mode
        if not linked:
            com = base.Shape.common(tool.Shape)
        # the hard mode
        else:
            attached = None
            invert = False
            # we have to figure out which was attached to which
            # sometimes the base can be attached to the tool
            if sbase.AttachedTo.split('#')[0] == stool.Name:
                attached = sbase
                invert = True
            elif stool.AttachedTo.split('#')[0] == sbase.Name:
                attached = stool
            else:
                FreeCAD.Console.PrintError("not attached")
                return
            placement = attached.LinkPlacement
            pat = doc.getObject(attached.AttachedTo.split('#')[0])
            while pat != None:
                placement = placementSub(placement, pat.Placement)
                pat = doc.getObject(pat.AttachedTo.split('#')[0])
            if invert:
                tool.Placement = placement.inverse()
            else:
                tool.Placement = placement
            com = base.Shape.common(tool.Shape)
        comp = doc.addObject("Part::Feature", "Common")
        comp.Shape = com
        cl = comp.Shape.BoundBox.ZLength
        vec = base.Placement.Rotation.multVec(FreeCAD.Vector(0,0,1))
        view = Draft.makeShape2DView(comp, vec)
        view.recompute()
        shp = view.Shape
        wire = TechDraw.findOuterWire(shp.Edges)
        if not debug:
            doc.removeObject(view.Name)
            doc.removeObject(comp.Name)
        face = Part.Face(wire)
        extr = face.extrude(base.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, cl)))
        cut = base.Shape.cut(extr)
        if not debug:
            doc.removeObject(base.Name)
            doc.removeObject(tool.Name)
        if keepLargest:
            shps = sorted(cut.SubShapes, key=lambda s: s.Volume)
            obj.Shape = shps[-1]
        else:
            obj.Shape = cut
        if obj.getParent() == None and obj.Base.getParent() != None:
            obj.Base.getParent().addObject(obj)
        else:
            obj.Placement = pl
            obj.Base.Visibility = False

class ViewProviderStraightCut:
    def __init__(self, obj):
        obj.Proxy = self
        self.Object = obj.Object

    def attach(self, obj):
        self.Object = obj.Object
        return

    def claimChildren(self):
        objs = []
        if not (self.Object.TypeId == 'Part::FeaturePython' and self.Object.AttachedTool):
            objs.append(self.Object.Tool)
        if self.Object.TypeId == 'Part::FeaturePython':
            objs.append(self.Object.Base)
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
3. Click this tool"""
            }

  def Activated(self):
    doc = FreeCAD.ActiveDocument
    sel = FreeCADGui.Selection.getSelection()
    if sel[0].TypeId == 'PartDesign::Body' or \
        sel[0].isDerivedFrom('PartDesign::Feature') or \
        (sel[0].TypeId == 'App::Link' and sel[0].LinkedObject.TypeId == 'PartDesign::Body'):
        obj = doc.addObject('PartDesign::FeaturePython', "StraightCut")
    elif sel[0].isDerivedFrom('Part::Feature') and sel[1].isDerivedFrom('Part::Feature'):
        obj = doc.addObject('Part::FeaturePython', "StraightCut")
    else:
        FreeCAD.Console.PrintError("can't use selection")
        return
    doc.openTransaction("StraightCut")
    StraightCut(obj)
    ViewProviderStraightCut(obj.ViewObject)
    doc.commitTransaction()
    doc.recompute()
    return

  def IsActive(self):
    if len(FreeCADGui.Selection.getSelection()) != 2 :
      return False
    return True

FreeCADGui.addCommand("StraightCut", AddStraightCut())
