import FreeCADGui
import wacky_locator

__dir__ = os.path.dirname(wacky_locator.__file__)
global icon
icon = os.path.join(__dir__, 'Wacky.svg')

class WackyWorkbench (Workbench):
    MenuText = "Wacky"
    Icon = icon
    def Initialize(self):
    	import StraightCut
    	import ExportDXF
    	self.appendToolbar("Wacky", ["StraightCut", "ExportDXF"])

FreeCADGui.addWorkbench(WackyWorkbench())

