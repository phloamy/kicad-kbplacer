from pcbnew import *
import wx
import os
import sys
import json
import itertools
import logging
import math


class KeyPlacer():
    def __init__(self, logger, board, layout, referenceLabel, originPoint=wxPointMM(0, 0)):
        self.logger = logger
        self.board = board
        self.layout = layout
        self.keyDistance = 19050000
        self.currentKey = 1
        self.currentDiode = 1
        self.referenceCoordinate = originPoint

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
        key = self.GetModule(keyFormat.format(self.referenceLabel[self.currentKey - 1]))
        self.currentKey += 1
        return key


    def GetCurrentDiodeCustom(self, diodeFormat):
        diode = self.GetModule(diodeFormat.format(self.referenceLabel[self.currentDiode - 1]))
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


    def Run(self, keyFormat, diodeFormat, routeTracks=False, rotateModules=True, useNorthFacingSwitches=False, relativeDiodePosition=wx.RealPoint(0, 0), relativeDiodeRotation=270, useCustomAnnotationFormat=False):
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

            self.SetRelativePositionMM(diodeModule, position, [relativeDiodePosition.x, relativeDiodePosition.y])

            if not diodeModule.IsFlipped():
                diodeModule.Flip(diodeModule.GetPosition())

            if rotateModules == True:

                rotationReference = wxPoint(
                            self.referenceCoordinate.x + (self.keyDistance * key["rotation_x"]),
                            self.referenceCoordinate.y + (self.keyDistance * key["rotation_y"])
                            )

                angle = key["rotation_angle"] * -10

                if useNorthFacingSwitches == True:
                    keyModule.SetOrientationDegrees(0)
                else:
                    keyModule.SetOrientationDegrees(180)
                keyModule.Rotate(rotationReference, angle)
                self.logger.info('Rotated key module to {}'.format(angle))

                diodeModule.SetOrientationDegrees(relativeDiodeRotation)
                diodeModule.Rotate(rotationReference, angle)
                self.logger.info('Rotated diode module to {}'.format(angle))

            if routeTracks == True:
                self.RouteKeyWithDiode(keyModule, diodeModule)
                self.RouteColumn(keyModule)


class KeyAutoPlaceDialog(wx.Dialog):
    def __init__(self, parent, title, caption):
        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        super(KeyAutoPlaceDialog, self).__init__(parent, -1, title, style=style)

        rows = []

        for i in range(9):
            rows.append(wx.BoxSizer(wx.HORIZONTAL))

        # row 0
        filePickerLabel = wx.StaticText(self, -1, "Select kle json file:")
        rows[0].Add(filePickerLabel, 0, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)

        filePicker = wx.FilePickerCtrl(self, -1)
        rows[0].Add(filePicker, 1, wx.EXPAND|wx.ALL, 5)

        # row 1
        keyAnnotationLabel = wx.StaticText(self, -1, "Key annotation format string:")
        rows[1].Add(keyAnnotationLabel, 1, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)

        keyAnnotationFormat = wx.TextCtrl(self, value='K_{}')
        rows[1].Add(keyAnnotationFormat, 1, wx.EXPAND | wx.ALL, 5)

        # row 2
        diodeAnnotationLabel = wx.StaticText(self, -1, "Diode annotation format string:")
        rows[2].Add(diodeAnnotationLabel, 1, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)

        diodeAnnotationFormat = wx.TextCtrl(self, value='D_{}')
        rows[2].Add(diodeAnnotationFormat, 1, wx.EXPAND|wx.ALL, 5)

        # row 3
        tracksCheckbox = wx.CheckBox(self, label="Add tracks")
        tracksCheckbox.SetValue(False)
        rows[3].Add(tracksCheckbox, 1, wx.EXPAND|wx.ALL, 5)

        disableRotationCheckbox = wx.CheckBox(self, label="Disable rotations")
        disableRotationCheckbox.SetValue(False)
        rows[3].Add(disableRotationCheckbox, 1, wx.EXPAND|wx.ALL, 5)

        northFacingSwitchCheckbox = wx.CheckBox(self, label="Use north-facing switches")
        rows[3].Add(northFacingSwitchCheckbox, 1, wx.EXPAND | wx.ALL, 5)

        # row 4
        diodePositionLabel = wx.StaticText(self, -1, "Relative diode position:")
        rows[4].Add(diodePositionLabel, 1, wx.LEFT|wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 5)

        diodePositionX = wx.SpinCtrlDouble(self, value='0')
        rows[4].Add(diodePositionX, 1, wx.EXPAND | wx.ALL, 5)

        diodePositionY = wx.SpinCtrlDouble(self, value='-5.05')
        rows[4].Add(diodePositionY, 1, wx.EXPAND | wx.ALL, 5)

        # row 5
        diodeRotationLabel = wx.StaticText(self, -1, "Relative diode rotation:")
        rows[5].Add(diodeRotationLabel, 1, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)

        diodeRotation = wx.SpinCtrlDouble(self, value='180')
        rows[5].Add(diodeRotation, 1, wx.EXPAND | wx.ALL, 5)

        # row 6
        originPointLabel = wx.StaticText(self, -1, "Origin point:")
        rows[6].Add(originPointLabel, 1, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)

        originPointX = wx.SpinCtrlDouble(self, value='0')
        rows[6].Add(originPointX, 1, wx.EXPAND | wx.ALL, 5)

        originPointY = wx.SpinCtrlDouble(self, value='0')
        rows[6].Add(originPointY, 1, wx.EXPAND | wx.ALL, 5)

        # row 7
        customAnnotationFormatCheckbox = wx.CheckBox(self, label="Use custom reference names")
        customAnnotationFormatCheckbox.SetValue(True)
        rows[7].Add(customAnnotationFormatCheckbox, 1, wx.EXPAND | wx.ALL, 5)

        customAnnotationSimpleFileCheckbox = wx.CheckBox(self, label="Use simple reference name file") # list references in a txt file and separate each reference with a new line
        customAnnotationSimpleFileCheckbox.SetValue(True)
        rows[7].Add(customAnnotationSimpleFileCheckbox, 1, wx.EXPAND | wx.ALL, 5)

        # row 8
        customAnnotationLabel = wx.StaticText(self, -1, "Select custom annotation json file:")
        rows[8].Add(customAnnotationLabel, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)

        filePicker2 = wx.FilePickerCtrl(self, -1)
        rows[8].Add(filePicker2, 1, wx.EXPAND | wx.ALL, 5)

        box = wx.BoxSizer(wx.VERTICAL)

        for row in rows:
            box.Add(row, 0, wx.EXPAND|wx.ALL, 5)

        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        box.Add(buttons, 0, wx.EXPAND|wx.ALL, 5)

        self.SetSizerAndFit(box)
        self.filePicker = filePicker
        self.keyAnnotationFormat = keyAnnotationFormat
        self.diodeAnnotationFormat = diodeAnnotationFormat
        self.tracksCheckbox = tracksCheckbox
        self.disableRotationCheckbox = disableRotationCheckbox
        self.northFacingSwitchChekbox = northFacingSwitchCheckbox
        self.diodePositionX = diodePositionX
        self.diodePositionY = diodePositionY
        self.diodeRotation = diodeRotation
        self.originPointX = originPointX
        self.originPointY = originPointY
        self.customAnnotationFormatCheckbox = customAnnotationFormatCheckbox
        self.customAnnotationSimpleFileCheckbox = customAnnotationSimpleFileCheckbox
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
        return not self.disableRotationCheckbox.GetValue()


    def IsNorthFacing(self):
        return self.northFacingSwitchChekbox.GetValue()


    def GetRelativeDiodePosition(self):
        return wx.RealPoint(self.diodePositionX.GetValue(), self.diodePositionY.GetValue())


    def GetRelativeDiodeRotation(self):
        return self.diodeRotation.GetValue()


    def GetOriginPoint(self):
        return wxPointMM(self.originPointX.GetValue(), self.originPointY.GetValue())


    def IsUsingCustomAnnotationFormat(self):
        return self.customAnnotationFormatCheckbox.GetValue()


    def IsUsingSimpleFile(self):
        return self.customAnnotationSimpleFileCheckbox.GetValue()


    def GetCustomAnnotationPath(self):
        return self.filePicker2.GetPath()

        
class KeyAutoPlace(ActionPlugin):
    def defaults(self):
        self.name = "KeyAutoPlaceRevamp"
        self.category = "Mechanical Keyboard Helper"
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

                annotationLabelPath = dlg.GetCustomAnnotationPath()

                if dlg.IsUsingSimpleFile():
                    referenceLabel = []

                    with open(annotationLabelPath) as file:
                        for line in file:
                            referenceLabel.append(line.replace("\n", ""))

                    self.logger.info("User annotations: {}".format(referenceLabel))

                else:
                    f2 = open(annotationLabelPath, "r")
                    textInput2 = f2.read()
                    f2.close()
                    referenceLabel = json.loads(textInput2)["annotations"]
                    self.logger.info("User annotations: {}".format(referenceLabel))

            placer = KeyPlacer(self.logger, self.board, layout, referenceLabel, dlg.GetOriginPoint())
            placer.Run(dlg.GetKeyAnnotationFormat(), dlg.GetDiodeAnnotationFormat(), dlg.IsTracks(), dlg.IsRotation(), dlg.IsNorthFacing(), dlg.GetRelativeDiodePosition(), dlg.GetRelativeDiodeRotation(), dlg.IsUsingCustomAnnotationFormat())


        dlg.Destroy()
        logging.shutdown()


KeyAutoPlace().register()
