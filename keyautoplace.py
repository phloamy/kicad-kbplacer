from pcbnew import *
import wx
import os
import sys
import json
import itertools
import logging
import math


class KeyPlacer():
    def __init__(self, logger, board, layout, referenceLabel):
        self.logger = logger
        self.board = board
        self.layout = layout
        self.keyDistance = 19050000
        self.currentKey = 1
        self.currentDiode = 1
        self.referenceCoordinate = wxPointMM(0, 0)

        self.referenceLabel = referenceLabel


    def GetModule(self, reference):
        self.logger.info('Searching for {} module'.format(reference))
        module = self.board.FindModuleByReference(reference)
        if module == None:
            self.logger.error('Module not found')
            raise Exception('Cannot find module {}'.format(reference))
        return module

    def GetCurrentKey(self, keyFormat):
        key = self.GetModule(keyFormat.format(self.currentKey))
        self.currentKey += 1
        return key

    
    def GetCurrentDiode(self, diodeFormat):
        diode = self.GetModule(diodeFormat.format(self.currentDiode))
        self.currentDiode += 1
        return diode


    def GetCurrentKeyCustom(self, keyFormat):
        self.logger.info('Getting current key from index: {}'.format(self.currentKey - 1))
        key = self.GetModule(keyFormat.format(self.referenceLabel["annotations"][self.currentKey - 1]))
        self.currentKey += 1
        return key


    def GetCurrentDiodeCustom(self, diodeFormat):
        diode = self.GetModule(diodeFormat.format(self.referenceLabel["annotations"][self.currentDiode - 1]))
        self.currentDiode += 1
        return diode


    def SetPosition(self, module, position):
        self.logger.info('Setting {} module position: {}'.format(module.GetReference(), position))
        module.SetPosition(position)


    def SetRelativePositionMM(self, module, referencePoint, direction):
        position = wxPoint(referencePoint.x + FromMM(direction[0]), referencePoint.y + FromMM(direction[1]))
        self.SetPosition(module, position)


    def AddTrackSegment(self, start, vector, layer=B_Cu):
        track = TRACK(self.board)
        track.SetWidth(FromMM(0.25))
        track.SetLayer(layer)
        track.SetStart(start)
        segmentEnd = wxPoint(track.GetStart().x + FromMM(vector[0]), track.GetStart().y + FromMM(vector[1]))
        track.SetEnd(segmentEnd)

        self.logger.info('Adding track segment ({}): [{}, {}]'.format(self.board.GetLayerName(layer), start, segmentEnd))
        self.board.Add(track)

        track.SetLocked(True)
        return segmentEnd


    def RouteKeyWithDiode(self, key, diode):
        end = self.AddTrackSegment(diode.FindPadByName('2').GetPosition(), [-1.98, -1.98])
        self.AddTrackSegment(end, [0, -4.2])


    def RouteColumn(self, key):
        segmentStart = wxPoint(key.GetPosition().x - FromMM(3.11), key.GetPosition().y - FromMM(1.84))
        self.AddTrackSegment(segmentStart, [0, 10], layer=F_Cu)


    def Run(self, keyFormat, diodeFormat, routeTracks=False, rotateModules=False, useCustomAnnotationFormat=False):
        for key in self.layout["keys"]:

            position = wxPoint(
                self.referenceCoordinate.x + (self.keyDistance * key["x"]) + (self.keyDistance * key["width"] // 2),
                self.referenceCoordinate.y + (self.keyDistance * key["y"]) + (self.keyDistance * key["height"] // 2))

            keyModule = None
            if useCustomAnnotationFormat == True:
                keyModule = self.GetCurrentKeyCustom(keyFormat)
            else:
                keyModule = self.GetCurrentKey(keyFormat)

            self.SetPosition(keyModule, position)


            diodeModule = None
            if useCustomAnnotationFormat == True:
                diodeModule = self.GetCurrentDiodeCustom(diodeFormat)
            else:
                diodeModule = self.GetCurrentDiode(diodeFormat)

            self.SetRelativePositionMM(diodeModule, position, [0, -5.05])

            if not diodeModule.IsFlipped():
                diodeModule.Flip(diodeModule.GetPosition())

            # something is not quite right, not recomented to use it yet:
            if rotateModules == True:

                rotationReference = wxPoint(
                            self.referenceCoordinate.x + (self.keyDistance * key["rotation_x"]),
                            self.referenceCoordinate.y + (self.keyDistance * key["rotation_y"])
                            )

                angle = key["rotation_angle"] * -10

                keyModule.SetOrientationDegrees(180)
                keyModule.Rotate(rotationReference, angle)
                self.logger.info('Rotated key module to {}'.format(angle))

                diodeModule.SetOrientationDegrees(180)
                diodeModule.Rotate(rotationReference, angle)
                self.logger.info('Rotated diode module to {}'.format(angle))

            if routeTracks == True:
                self.RouteKeyWithDiode(keyModule, diodeModule)
                self.RouteColumn(keyModule)


class KeyAutoPlaceDialog(wx.Dialog):
    def __init__(self, parent, title, caption):
        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        super(KeyAutoPlaceDialog, self).__init__(parent, -1, title, style=style)
        row1 = wx.BoxSizer(wx.HORIZONTAL)

        text = wx.StaticText(self, -1, "Select kle json file:")
        row1.Add(text, 0, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)

        filePicker = wx.FilePickerCtrl(self, -1)
        row1.Add(filePicker, 1, wx.EXPAND|wx.ALL, 5)

        row2 = wx.BoxSizer(wx.HORIZONTAL)

        keyAnnotationLabel = wx.StaticText(self, -1, "Key annotation format string:")
        row2.Add(keyAnnotationLabel, 1, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)

        keyAnnotationFormat = wx.TextCtrl(self, value='K_{}')
        row2.Add(keyAnnotationFormat, 1, wx.EXPAND|wx.ALL, 5)

        row3 = wx.BoxSizer(wx.HORIZONTAL)

        diodeAnnotationLabel = wx.StaticText(self, -1, "Diode annotation format string:")
        row3.Add(diodeAnnotationLabel, 1, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)

        diodeAnnotationFormat = wx.TextCtrl(self, value='D_{}')
        row3.Add(diodeAnnotationFormat, 1, wx.EXPAND|wx.ALL, 5)

        row4 = wx.BoxSizer(wx.HORIZONTAL)

        tracksCheckbox = wx.CheckBox(self, label="Add tracks")
        tracksCheckbox.SetValue(False)
        row4.Add(tracksCheckbox, 1, wx.EXPAND|wx.ALL, 5)

        rotationCheckbox = wx.CheckBox(self, label="Enable rotations")
        rotationCheckbox.SetValue(False)
        row4.Add(rotationCheckbox, 1, wx.EXPAND|wx.ALL, 5)

        # example: K_Backspace1

        row5 = wx.BoxSizer(wx.HORIZONTAL)

        customAnnotationFormatCheckbox = wx.CheckBox(self, label="Use custom annotation format to search for reference")
        customAnnotationFormatCheckbox.SetValue(True)
        row5.Add(customAnnotationFormatCheckbox, 1, wx.EXPAND | wx.ALL, 5)

        row6 = wx.BoxSizer(wx.HORIZONTAL)

        text2 = wx.StaticText(self, -1, "Select custom annotation json file:")
        row6.Add(text2, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)

        filePicker2 = wx.FilePickerCtrl(self, -1)
        row6.Add(filePicker2, 1, wx.EXPAND | wx.ALL, 5)

        box = wx.BoxSizer(wx.VERTICAL)

        box.Add(row1, 0, wx.EXPAND|wx.ALL, 5)
        box.Add(row2, 0, wx.EXPAND|wx.ALL, 5)
        box.Add(row3, 0, wx.EXPAND|wx.ALL, 5)
        box.Add(row4, 0, wx.EXPAND|wx.ALL, 5)
        box.Add(row5, 0, wx.EXPAND|wx.ALL, 5)
        box.Add(row6, 0, wx.EXPAND|wx.ALL, 5)

        buttons = self.CreateButtonSizer(wx.OK|wx.CANCEL)
        box.Add(buttons, 0, wx.EXPAND|wx.ALL, 5)

        self.SetSizerAndFit(box)
        self.filePicker = filePicker
        self.keyAnnotationFormat = keyAnnotationFormat
        self.diodeAnnotationFormat = diodeAnnotationFormat
        self.tracksCheckbox = tracksCheckbox
        self.rotationCheckbox = rotationCheckbox
        self.customAnnotationFormatCheckbox = customAnnotationFormatCheckbox
        self.filePicker2 = filePicker2


    def GetJsonPath(self):
        return self.filePicker.GetPath()


    def GetKeyAnnotationFormat(self):
        return self.keyAnnotationFormat.GetValue()


    def GetDiodeAnnotationFormat(self):
        return self.diodeAnnotationFormat.GetValue()


    def IsTracks(self):
        return self.tracksCheckbox.GetValue()


    def IsRotation(self):
        return self.rotationCheckbox.GetValue()


    def IsUsingCustomAnnotationFormat(self):
        return self.customAnnotationFormatCheckbox.GetValue()


    def GetCustomAnnotationJsonPath(self):
        return self.filePicker2.GetPath()

        
class KeyAutoPlace(ActionPlugin):
    def defaults(self):
        self.name = "KeyAutoPlaceRev1"
        self.category = "Mechanical Keybaord Helper"
        self.description = "Auto placement for key switches and diodes"


    def Initialize(self):
        self.board = GetBoard()

        # go to the project folder - so that log will be in proper place
        os.chdir(os.path.dirname(os.path.abspath(self.board.GetFileName())))

        # Remove all handlers associated with the root logger object.
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # set up logger
        logging.basicConfig(level=logging.DEBUG,
                            filename="keyautoplace.log",
                            filemode='w',
                            format='%(asctime)s %(name)s %(lineno)d:%(message)s',
                            datefmt='%m-%d %H:%M:%S')
        self.logger = logging.getLogger(__name__)
        self.logger.info("Plugin executed with python version: " + repr(sys.version))


    def Run(self):
        self.Initialize()

        pcbFrame = [x for x in wx.GetTopLevelWindows() if x.GetName() == 'PcbFrame'][0]

        dlg = KeyAutoPlaceDialog(pcbFrame, 'Title', 'Caption')
        if dlg.ShowModal() == wx.ID_OK:
            layoutPath = dlg.GetJsonPath()
            f = open(layoutPath, "r")
            textInput = f.read()
            f.close()
            layout = json.loads(textInput)
            self.logger.info("User layout: {}".format(layout))

            referenceLabel = None

            if dlg.IsUsingCustomAnnotationFormat() == True:
                annotationLabelPath = dlg.GetCustomAnnotationJsonPath()
                f2 = open(annotationLabelPath, "r")
                textInput2 = f2.read()
                f2.close()
                referenceLabel = json.loads(textInput2)
                self.logger.info("User annotations: {}".format(referenceLabel))

            placer = KeyPlacer(self.logger, self.board, layout, referenceLabel)
            placer.Run(dlg.GetKeyAnnotationFormat(), dlg.GetDiodeAnnotationFormat(), dlg.IsTracks(), dlg.IsRotation(), dlg.IsUsingCustomAnnotationFormat())


        dlg.Destroy()
        logging.shutdown()


KeyAutoPlace().register()
