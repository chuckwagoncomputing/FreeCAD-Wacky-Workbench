from PySide import QtCore, QtGui
import FreeCAD, FreeCADGui, Part, os, importDXF

__dir__ = os.path.dirname(__file__)

class ExportDXF():
    def __init__(self, obj):
        self.Type = "exportdxf"
        obj.addProperty("App::PropertyLink", "Face", "ExportDXF", "Face to export")
        obj.addProperty("App::PropertyFile", "File", "ExportDXF", "DXF file to export to")
        obj.addProperty("App::PropertyBool", "Relative", "ExportDXF", "Relative to document location?")
        obj.Proxy = self

    def execute(self, obj):
        doc = FreeCAD.ActiveDocument
        sel = FreeCADGui.Selection.getSelection()
        file = ""
        if obj.Relative:
            file = os.path.abspath(os.path.join(os.path.dirname(FreeCAD.ActiveDocument.FileName), obj.File))
        else:
            file = obj.File
        if obj.Face is None:
            if len(sel) == 1:
                obj.Face = sel[0]
                obj.Face.Parents[0][0].addObject(obj)
            else:
                FreeCAD.Console.PrintError("Must select a face")
                return
        if hasattr(importDXF, "exportOptions"):
            options = importDXF.exportOptions(file)
            importDXF.export(obj.Face, file, options)
        else:
            importDXF.export(obj.Face, file)

class ViewProviderExportDXF:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
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
        return os.path.join(__dir__, 'ExportDXF.svg')

    def setEdit(self,vobj,mode):
        taskd = ExportPanel()
        taskd.obj = vobj.Object
        taskd.update()
        FreeCADGui.Control.showDialog(taskd)
        return True

    def unsetEdit(self,vobj,mode):
        FreeCADGui.Control.closeDialog()
        return False

    def __getstate__(self):
        return None

    def __setstate__(self,state):
        return None

class AddExportDXF:
  def GetResources(self):
    return {'Pixmap' : os.path.join(__dir__, 'ExportDXF.svg'),
            'MenuText': 'Export DXF',
            'Accel': "E",
            'ToolTip' : """
                Export a face to DXF, keeping it in sync with model changes
                1. Select a face
                2. Click this tool
            """}

  def Activated(self):
    FreeCADGui.Control.showDialog(ExportPanel())
    return

  def IsActive(self):
    if len(FreeCADGui.Selection.getSelection()) < 1 :
      return False
    return True

class ExportPanel:
    def __init__(self):
        self.obj = None
        path = os.path.join(__dir__, "File.ui")
        self.form = FreeCADGui.PySideUic.loadUi(path)
        self.form.radioRelative.setChecked(True)
        self.form.buttonBrowse.clicked.connect(self.pickSaveFile)
        FreeCAD.ActiveDocument.openTransaction("Export DXF")

    def pickSaveFile(self):
        filename, filter = QtGui.QFileDialog.getSaveFileName(self.form, 'Save file', '.', 'Autocad DXF 2D (*.dxf)')
        if filename:
            self.form.lineEditFile.setText(filename)

    def update(self):
        if self.obj:
            if self.obj.Relative:
                self.form.radioRelative.setChecked(True)
                self.form.lineEditFile.setText(os.path.abspath(os.path.join(os.path.dirname(FreeCAD.ActiveDocument.FileName), self.obj.File)))
            else:
                self.form.radioAbsolute.setChecked(True)
                self.form.lineEditFile.setText(self.obj.File)

    def accept(self):
        file = self.form.lineEditFile.text()
        filename = os.path.splitext(os.path.basename(file))[0]
        if not self.obj:
            doc = FreeCAD.ActiveDocument
            self.obj = doc.addObject('Part::FeaturePython', "ExportDXF " + filename)
            ExportDXF(self.obj)
            ViewProviderExportDXF(self.obj.ViewObject)
        self.obj.Relative = self.form.radioRelative.isChecked()
        if self.obj.Relative:
            self.obj.File = os.path.relpath(file, os.path.dirname(FreeCAD.ActiveDocument.FileName))
        else:
            self.obj.File = file
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCADGui.ActiveDocument.resetEdit()
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()

    def reject(self):
        FreeCAD.ActiveDocument.abortTransaction()
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()

FreeCADGui.addCommand("ExportDXF", AddExportDXF())
