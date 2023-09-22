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
        # s[base|tool] = selected, or link if the selection is in a link
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

                # If there is an assembly, and the selection has a parent(i.e. the selection is a Body inside a Part)
                if hasattr(doc, 'Assembly') and sbase.getParent():
                    # Filter the part's InList for links with the selection inside.
                    lbase = list(filter(lambda o: o.TypeId == 'App::Link' and \
                        FreeCADGui.Selection.isSelected(doc.Assembly, o.Name + "." + sbase.Name + "."), sbase.getParent().InList))
                # If a link is selected
                if sbase.TypeId == 'App::Link':
                    # store the name of the link as a string
                    obj.AttachedBase = sbase.Name
                    # store the linked object as the base
                    obj.Base = sbase.LinkedObject
                    linked = True
                # If our filter found something
                elif lbase:
                    # Store the name of the link as a string
                    obj.AttachedBase = lbase[0].Name
                    # Store the selected object as the base.
                    # The link is automatically dereferenced since we're not dealing with the link itself,
                    #   but rather a child of it.
                    obj.Base = sbase
                    # Use the link as the selection for computation
                    sbase = lbase[0]
                    linked = True
                # No link involved
                else:
                    obj.Base = sbase

                # We do the same thing for the tool as we did for the part.
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

        # Check if the base is a Part or PartDesign Feature
        if obj.Base.isDerivedFrom('PartDesign::Feature'):
            # If it's a PartDesign Feature, we need to make the body the base for computation
            base = obj.Base.getParent()
            # If our StraightCut object is the tip of the body
            if base.Tip == obj:
                # Store the BaseFeature to use for recompute
                obj.Base = obj.BaseFeature
        elif obj.Base.isDerivedFrom('Part::Feature'):
            base = obj.Base

        # Only on initial generation
        if not recompute:
            # Store the tip of the body
            if obj.Base.TypeId == 'PartDesign::Body':
                obj.Base = obj.Base.Tip

            # Create ShapeBinder of the tool to avoid loops
            if obj.Tool.TypeId == 'PartDesign::Body' or obj.Tool.isDerivedFrom('PartDesign::Feature'):
                if base.TypeId == 'PartDesign::Body':
                    shb = base.newObject('PartDesign::ShapeBinder','ShapeBinder')
                else:
                    shb = doc.addObject('PartDesign::ShapeBinder','ShapeBinder')
                shb.Support = [obj.Tool,'']
                # This is important to keep everything positioned properly
                shb.TraceSupport = True
                obj.Tool = shb
                shb.recompute()
                shb.Visibility = False

        # Use the stored tool for computation
        tool = obj.Tool

        # If we're working with a PartDesign Body, we need to keep only one resulting solid
        if obj.TypeId == 'PartDesign::FeaturePython':
            keepLargest = True

        # common shape, which will be generated differently in different scenarios
        com = None
        # In this section we make some temporary Parts, and move the temporary base part flat to the coordinate plane.
        # This is necessary because Draft makeShape2DView places the 2D view on the plane.
        # We need to copy placements so we don't edit the original placement, touching its object.
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
            # Move the (temp) tool by the same amount that the (temp) base was moved.
            ttb.Placement = placementSub(tp, pl)
        # Use our temporary Parts for computation
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
            # Subtract all placements until we get back to the origin.
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
        # The height of the intersection will be used as the distance to pocket
        cl = comp.Shape.BoundBox.ZLength
        # Get the vector of the base's Z axis
        vec = base.Placement.Rotation.multVec(FreeCAD.Vector(0,0,1))
        view = Draft.makeShape2DView(comp, vec)
        view.recompute()
        shp = view.Shape
        wire = TechDraw.findOuterWire(shp.Edges)
        if not debug:
            doc.removeObject(view.Name)
            doc.removeObject(comp.Name)
        face = Part.Face(wire)
        # Extrude by the Z height we got earlier
        extr = face.extrude(base.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, cl)))
        cut = base.Shape.cut(extr)
        if not debug:
            doc.removeObject(base.Name)
            doc.removeObject(tool.Name)
        if keepLargest:
            # Sort solids by volume and keep the largest
            shps = sorted(cut.SubShapes, key=lambda s: s.Volume)
            obj.Shape = shps[-1]
        else:
            obj.Shape = cut
        # If the base has a parent, we'll make our StraightCut object a child of it
        if obj.getParent() == None and obj.Base.getParent() != None:
            obj.Base.getParent().addObject(obj)
        # Part or Feature with no container, needs its own placement
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
        # If it's a Part in a link, don't claim the tool
        if not (self.Object.TypeId == 'Part::FeaturePython' and self.Object.AttachedTool):
            objs.append(self.Object.Tool)
        # Claim the base if it's a Part
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
